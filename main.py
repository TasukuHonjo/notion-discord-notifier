# main.py
import os
import requests
import datetime
import time

NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
DATABASE_ID = os.environ.get("DATABASE_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
# 以下はNotionのプロパティ名（必要なら編集）
DATE_PROP = os.environ.get("NOTION_DATE_PROP", "Date")
TITLE_PROP = os.environ.get("NOTION_TITLE_PROP", "Name")
NOTIFIED_PROP = os.environ.get("NOTION_NOTIFIED_PROP", "Notified")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def query_today_pages():
    """Notion データベースから今日の予定を取得（Date プロパティ equals today）"""
    today = datetime.date.today().isoformat()
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": DATE_PROP,
            "date": {"equals": today}
        }
    }
    r = requests.post(url, json=payload, headers=NOTION_HEADERS)
    r.raise_for_status()
    data = r.json()
    return data.get("results", [])

def get_title(page):
    """ページのタイトルを取得（Name プロパティ想定）"""
    prop = page["properties"].get(TITLE_PROP)
    if not prop:
        return "(no title)"
    # title プロパティ構造からテキスト抽出
    title_parts = prop.get("title", [])
    return "".join([t.get("plain_text","") for t in title_parts]) or "(no title)"

def is_notified(page):
    """Notified(Checkbox)があるか確認。なければ False とみなす"""
    prop = page["properties"].get(NOTIFIED_PROP)
    if not prop:
        return False
    # checkbox プロパティは "checkbox": true/false
    return bool(prop.get("checkbox", False))

def mark_notified(page_id):
    """Notion のページの Notified を true にする（PATCH）"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            NOTIFIED_PROP: {
                "checkbox": True
            }
        }
    }
    r = requests.patch(url, json=payload, headers=NOTION_HEADERS)
    r.raise_for_status()
    return r.json()

def send_discord(message):
    payload = {"content": message}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    r.raise_for_status()
    return r

def main():
    # 必要環境変数チェック
    for var in ("NOTION_API_KEY", "DATABASE_ID", "DISCORD_WEBHOOK_URL"):
        if not os.environ.get(var):
            raise SystemExit(f"Missing env var: {var}")

    pages = query_today_pages()
    if not pages:
        print("No events for today.")
        return

    for p in pages:
        page_id = p["id"]
        title = get_title(p)
        if is_notified(p):
            print(f"Already notified: {title} (page {page_id})")
            continue

        # 通知文を作る（自由に編集可能）
        message = f"📅 本日の予定: **{title}** が来ています！"
        try:
            send_discord(message)
            print(f"Notified Discord for: {title}")
            # 通知したら Notion のチェックボックスをオンにする（再通知防止）
            mark_notified(page_id)
            # Notion API レート避けのため少し待つ
            time.sleep(1)
        except Exception as e:
            print("Error notifying for", title, e)

if __name__ == "__main__":
    main()
