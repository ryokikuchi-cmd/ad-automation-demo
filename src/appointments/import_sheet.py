"""② 商談スプシ取込。クライアント記入の特定スプシを読み取り appointments へ反映。

実データ形式（AIレポート/キープサーチ/商談データ）に準拠:
  年月（YYYY-MM, 月次）/ 広告セット / 商談数 (+任意 広告/成約数)
  → 広告セット単位・月次の商談数。結合キーは「広告セット」。

設計: read（gspread・I/O）と parse/upsert（純粋・DB）を分離してテスト可能に。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..db.models import Appointment


@dataclass
class ImportReport:
    imported: int = 0
    skipped: int = 0
    unmatched_adsets: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ----- read層（gspread。I/O依存） -----

def read_sheet_rows(sheet_cfg: dict) -> list[dict]:
    """特定のGoogleスプシをgspreadで読み取り、ヘッダ付きdictのリストを返す。

    sheet_cfg: {spreadsheet_id, worksheet, (任意)service_account_json}
    認証: GOOGLE_SERVICE_ACCOUNT_JSON（env or cfg）のサービスアカウント。
    """
    import gspread

    sa_path = sheet_cfg.get("service_account_json")
    gc = gspread.service_account(filename=sa_path) if sa_path else gspread.service_account()
    ws = gc.open_by_key(sheet_cfg["spreadsheet_id"]).worksheet(sheet_cfg["worksheet"])
    return ws.get_all_records()  # 1行目をヘッダとしたdictのリスト


# ----- parse/validate層（純粋・テスト可能） -----

def _parse_month_or_date(value) -> date:
    """'2026-04'（年月）→ 月初日 / '2026-04-15'（日付）→ その日。"""
    s = str(value).strip()
    parts = s.split("-")
    if len(parts) == 2:  # YYYY-MM
        return date(int(parts[0]), int(parts[1]), 1)
    return date.fromisoformat(s[:10])


def parse_rows(rows: list[dict], column_map: dict,
               known_adsets: set[str] | None = None) -> tuple[list[dict], ImportReport]:
    """シート行を appointments レコードへ正規化＋バリデーション。

    column_map: テンプレ列名 → 内部フィールド（date/adset/ad/appointments/won）
    known_adsets: ads/rawに存在する広告セット名の集合（不一致検知用・任意）
    """
    rep = ImportReport()
    out: list[dict] = []
    c_date = column_map.get("date", "年月")
    c_adset = column_map.get("adset", "広告セット")
    c_ad = column_map.get("ad", "広告")
    c_appt = column_map.get("appointments", "商談数")
    c_won = column_map.get("won", "成約数")

    for i, r in enumerate(rows, start=2):  # 2=ヘッダ次の行
        adset = str(r.get(c_adset, "")).strip()
        raw_date = r.get(c_date, "")
        raw_appt = r.get(c_appt, "")
        if not adset or raw_date in ("", None) or raw_appt in ("", None):
            rep.skipped += 1
            rep.errors.append(f"行{i}: 必須列(年月/広告セット/商談数)欠損")
            continue
        try:
            d = _parse_month_or_date(raw_date)
            appt = int(raw_appt)
        except (ValueError, TypeError) as ex:
            rep.skipped += 1
            rep.errors.append(f"行{i}: 形式不正 ({ex})")
            continue
        if known_adsets is not None and adset not in known_adsets:
            rep.unmatched_adsets.append(adset)
        out.append({
            "date": d, "adset": adset,
            "ad": (str(r.get(c_ad)).strip() or None) if r.get(c_ad) else None,
            "appointments": appt,
            "won": int(r.get(c_won) or 0) if str(r.get(c_won, "")).strip() else 0,
        })
    rep.imported = len(out)
    return out, rep


# ----- upsert層（DB） -----

def upsert_appointments(session, ad_account_id: int, records: list[dict], source: str) -> int:
    """source（スプシID!worksheet）単位で洗い替え（idempotent: 再取込で重複しない）。"""
    session.query(Appointment).filter(
        Appointment.ad_account_id == ad_account_id,
        Appointment.source_sheet == source,
    ).delete(synchronize_session=False)
    for rec in records:
        session.add(Appointment(ad_account_id=ad_account_id, source_sheet=source, **rec))
    session.commit()
    return len(records)


def import_appointments(session, ad_account, sheet_cfg: dict,
                        known_adsets: set[str] | None = None) -> ImportReport:
    """特定スプシを読み取り → 検証 → appointmentsへ反映（オーケストレーション）。"""
    rows = read_sheet_rows(sheet_cfg)
    records, rep = parse_rows(rows, sheet_cfg.get("columns", {}), known_adsets)
    source = f"{sheet_cfg['spreadsheet_id']}!{sheet_cfg['worksheet']}"
    upsert_appointments(session, ad_account.id, records, source)
    return rep
