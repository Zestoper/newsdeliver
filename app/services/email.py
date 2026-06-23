import os
import smtplib
import httpx
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)

SMTP_HOST = settings.SMTP_HOST
SMTP_PORT = settings.SMTP_PORT
SMTP_USER = settings.SMTP_USER
SMTP_PASSWORD = settings.SMTP_PASSWORD

_CAT_EMOJI = {
    "정치": "🏛", "경제": "💰", "IT": "💻", "문화": "🎭",
    "스포츠": "⚽", "예술": "🎨", "연예": "🎬", "국제": "🌐", "사회": "📋",
}


def _send_sendgrid(to_email: str, subject: str, html: str) -> None:
    resp = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}"},
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": SMTP_USER, "name": "News Delivery"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        },
        timeout=15,
    )
    resp.raise_for_status()


# ... (_card_html, _build_html 그대로 유지) ...


def send_newsletter(
    to_email: str,
    articles: list,
    base_url: str = "http://127.0.0.1:8000",
    category_name: str = "",
) -> bool:
    if not articles or not to_email:
        return False

    base_url = base_url.rstrip("/")
    cards = "".join(_card_html(a, base_url) for a in articles)
    cat_label = category_name or (articles[0].get("category_name") or "뉴스")
    cat_emoji = _CAT_EMOJI.get(cat_label, "📰")
    subject = f"[News Delivery] {cat_emoji} {cat_label} 최신 뉴스 {len(articles)}건"
    html_body = _build_html(cards, len(articles), base_url)

    try:
        if os.getenv("SENDGRID_API_KEY"):
            _send_sendgrid(to_email, subject, html_body)
            return True
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception:
        return False


def send_newsletters_batch(
    items: list[dict],
    base_url: str = "http://127.0.0.1:8000",
) -> list[bool]:
    if not items:
        return []

    results = [False] * len(items)
    base_url = base_url.rstrip("/")

    if os.getenv("SENDGRID_API_KEY"):
        for i, item in enumerate(items):
            try:
                to_email = item["email"]
                articles = item["articles"]
                category_name = item.get("category_name", "")
                if not articles or not to_email:
                    continue
                cards = "".join(_card_html(a, base_url) for a in articles)
                cat_label = category_name or (articles[0].get("category_name") or "뉴스")
                cat_emoji = _CAT_EMOJI.get(cat_label, "📰")
                subject = f"[News Delivery] {cat_emoji} {cat_label} 최신 뉴스 {len(articles)}건"
                html_body = _build_html(cards, len(articles), base_url)
                _send_sendgrid(to_email, subject, html_body)
                results[i] = True
            except Exception:
                results[i] = False
        return results

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            for i, item in enumerate(items):
                try:
                    to_email = item["email"]
                    articles = item["articles"]
                    category_name = item.get("category_name", "")
                    if not articles or not to_email:
                        continue
                    cards = "".join(_card_html(a, base_url) for a in articles)
                    cat_label = category_name or (articles[0].get("category_name") or "뉴스")
                    cat_emoji = _CAT_EMOJI.get(cat_label, "📰")
                    subject = f"[News Delivery] {cat_emoji} {cat_label} 최신 뉴스 {len(articles)}건"
                    html_body = _build_html(cards, len(articles), base_url)
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = subject
                    msg["From"] = SMTP_USER
                    msg["To"] = to_email
                    msg.attach(MIMEText(html_body, "html"))
                    server.sendmail(SMTP_USER, to_email, msg.as_string())
                    results[i] = True
                except Exception:
                    results[i] = False
    except Exception:
        pass

    return results


def send_verify_email(to_email: str, token: str, base_url: str = "http://127.0.0.1:8000") -> None:
    verify_url = f"{base_url.rstrip('/')}/verify-email?token={token}"
    subject = "[News Delivery] 이메일 인증을 완료해주세요"
    html_body = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:480px;margin:0 auto;padding:32px 16px;">
  <div style="background:linear-gradient(135deg,#cc0000,#ff4444);border-radius:12px 12px 0 0;padding:24px 28px;">
    <h1 style="color:white;font-size:20px;font-weight:900;margin:0;">📰 News Delivery</h1>
  </div>
  <div style="background:white;padding:32px 28px;border-radius:0 0 12px 12px;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
    <h2 style="font-size:19px;color:#1a1a1a;margin:0 0 12px;">이메일 인증</h2>
    <p style="font-size:15px;color:#555;line-height:1.8;margin:0 0 24px;">
      아래 버튼을 클릭하면 이메일 인증이 완료되고<br>뉴스레터 구독이 시작됩니다.
    </p>
    <a href="{verify_url}"
       style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#cc0000,#ff4444);
              color:white;text-decoration:none;border-radius:24px;font-weight:700;font-size:15px;
              box-shadow:0 4px 12px rgba(204,0,0,0.3);">
      ✅ 이메일 인증하기
    </a>
    <p style="font-size:12px;color:#adb5bd;margin:20px 0 0;">
      이 메일을 요청하지 않으셨다면 무시하셔도 됩니다.
    </p>
  </div>
  <p style="text-align:center;font-size:12px;color:#adb5bd;margin-top:16px;">© 2026 News Delivery</p>
</div>
</body>
</html>"""

    print(f"[EMAIL] 발송 시도: to={to_email}")
    if os.getenv("SENDGRID_API_KEY"):
        _send_sendgrid(to_email, subject, html_body)
        print(f"[EMAIL] SendGrid 발송 성공: {to_email}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[EMAIL] SMTP 발송 성공: {to_email}")
    except Exception as e:
        print(f"[EMAIL] 발송 실패: {e}")
        raise
