import os
import smtplib
import threading
from concurrent.futures import ThreadPoolExecutor
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


def _sender_email() -> str:
    """보내는 사람 주소. MAIL_FROM이 있으면 그 값을 쓰고 없으면 SMTP_USER를 쓴다."""
    return os.getenv("MAIL_FROM") or SMTP_USER


def _api_provider() -> str | None:
    """HTTPS API 발송 서비스 선택. Render 무료 플랜은 SMTP 포트를 막아서 API 발송이 필요하다."""
    if os.getenv("BREVO_API_KEY"):
        return "brevo"
    if os.getenv("SENDGRID_API_KEY"):
        return "sendgrid"
    return None


def _send_brevo(to_email: str, subject: str, html: str) -> None:
    resp = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": os.getenv("BREVO_API_KEY", ""), "accept": "application/json"},
        json={
            "sender": {"email": _sender_email(), "name": "News Delivery"},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html,
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        print(f"[EMAIL] Brevo 발송 실패 {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()


def _send_sendgrid(to_email: str, subject: str, html: str) -> None:
    resp = httpx.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}"},
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": _sender_email(), "name": "News Delivery"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        print(f"[EMAIL] SendGrid 발송 실패 {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()


def _send_api(to_email: str, subject: str, html: str) -> None:
    if _api_provider() == "brevo":
        _send_brevo(to_email, subject, html)
    else:
        _send_sendgrid(to_email, subject, html)


def _card_html(article: dict, base_url: str) -> str:
    news_id = article.get("id")
    title = article.get("title", "")
    source = article.get("source") or ""
    cat = article.get("category_name") or ""
    image_url = article.get("image_url") or ""
    content = article.get("content") or ""
    link = article.get("link") or (f"{base_url}/news/{news_id}" if news_id else "")

    ai_summary = article.get("ai_summary", "") or ""
    is_global = bool(article.get("is_global", 0))

    # 해외뉴스: EN::: ... \n KO::: ... 형식 파싱
    summary_block = ""
    if ai_summary and is_global and "EN:::" in ai_summary and "KO:::" in ai_summary:
        parts = ai_summary.split("KO:::", 1)
        en_text = parts[0].replace("EN:::", "").strip()
        ko_text = parts[1].strip() if len(parts) > 1 else ""
        summary_block = (
            f'<p style="font-size:11px;color:#0066cc;font-weight:700;margin:0 0 4px;">English Summary</p>'
            f'<p style="font-size:13px;color:#444;line-height:1.7;margin:0 0 12px;">{en_text}</p>'
            f'<p style="font-size:11px;color:#7c3aed;font-weight:700;margin:0 0 4px;">한국어 요약</p>'
            f'<p style="font-size:13px;color:#555;line-height:1.7;margin:0 0 16px;">{ko_text}</p>'
        )
    elif ai_summary:
        summary_block = (
            f'<p style="font-size:11px;color:#7c3aed;font-weight:700;margin:0 0 6px;">AI 요약</p>'
            f'<p style="font-size:14px;color:#555;line-height:1.75;margin:0 0 16px;">{ai_summary}</p>'
        )
    else:
        excerpt = content.replace("\n", " ").strip()[:120]
        if len(content.replace("\n", " ").strip()) > 120:
            excerpt += "…"
        summary_block = f'<p style="font-size:14px;color:#555;line-height:1.75;margin:0 0 16px;">{excerpt}</p>'

    cat_badge = (
        f'<span style="display:inline-block;background:#fff0f0;color:#c00;'
        f'font-size:11px;font-weight:700;padding:2px 9px;border-radius:12px;margin-bottom:10px;">'
        f'{cat}</span>' if cat else ""
    )

    image_block = (
        f'<img src="{image_url}" alt="{title}" '
        f'style="width:100%;height:180px;object-fit:cover;display:block;border-radius:6px 6px 0 0;">'
        if image_url and image_url.startswith("http") else ""
    )

    btn = (
        f'<a href="{link}" '
        f'style="display:inline-block;padding:9px 22px;background:#c00;color:white;'
        f'text-decoration:none;border-radius:20px;font-size:13px;font-weight:700;">기사 읽기</a>'
        if link else ""
    )

    return f"""
    <div style="background:white;border-radius:10px;margin-bottom:20px;
                box-shadow:0 2px 10px rgba(0,0,0,0.07);overflow:hidden;">
      {image_block}
      <div style="padding:20px 22px 22px;">
        {cat_badge}
        {'<p style="font-size:11px;color:#adb5bd;margin-bottom:6px;">'+source+'</p>' if source else ''}
        <h3 style="font-size:17px;font-weight:800;color:#1a1a1a;margin:0 0 10px;line-height:1.45;">{title}</h3>
        {summary_block}
        {btn}
      </div>
    </div>"""


def _build_html(cards: str, count: int, base_url: str) -> str:
    """뉴스레터 HTML 본문 조립 — send_newsletter / send_newsletters_batch 공용."""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;">
  <div style="background:linear-gradient(135deg,#cc0000,#ff4444);border-radius:12px 12px 0 0;
              padding:24px 28px;margin-bottom:0;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;background:rgba(255,255,255,0.2);border-radius:8px;flex-shrink:0;">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="4" width="14" height="2" rx="1" fill="white"/>
          <rect x="3" y="9" width="14" height="2" rx="1" fill="white"/>
          <rect x="3" y="14" width="9" height="2" rx="1" fill="white"/>
        </svg>
      </span>
      <span style="font-size:22px;font-weight:900;color:white;letter-spacing:-0.5px;">News<span style="color:rgba(255,255,255,0.75);">Deliver</span></span>
    </div>
    <h1 style="color:white;font-size:18px;font-weight:700;margin:0;letter-spacing:-0.5px;">오늘의 뉴스레터</h1>
    <p style="color:rgba(255,255,255,0.8);font-size:13px;margin:6px 0 0;">
      구독하신 카테고리의 최신 뉴스 <strong style="color:white;">{count}건</strong>을 전달해드립니다.
    </p>
  </div>
  <div style="height:4px;background:linear-gradient(90deg,#cc0000,#ff6b6b);margin-bottom:20px;"></div>
  {cards}
  <div style="text-align:center;padding:20px 0 8px;">
    <p style="font-size:13px;color:#868e96;margin:0 0 6px;">
      <a href="{base_url}" style="color:#c00;text-decoration:none;font-weight:700;">NewsDeliver</a> 뉴스레터
    </p>
    <p style="font-size:12px;color:#adb5bd;margin:0;">
      © 2026 News Delivery ·
      <a href="{base_url}/subscribe" style="color:#adb5bd;">구독 설정 변경</a>
    </p>
  </div>
</div>
</body>
</html>"""



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
    subject = f"[News Delivery] {cat_label} 최신 뉴스 {len(articles)}건"
    html_body = _build_html(cards, len(articles), base_url)

    try:
        if _api_provider():
            _send_api(to_email, subject, html_body)
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

    if _api_provider():
        def _one(i: int, item: dict) -> None:
            try:
                to_email = item["email"]
                articles = item["articles"]
                category_name = item.get("category_name", "")
                if not articles or not to_email:
                    return
                cards = "".join(_card_html(a, base_url) for a in articles)
                cat_label = category_name or (articles[0].get("category_name") or "뉴스")
                subject = f"[News Delivery] {cat_label} 최신 뉴스 {len(articles)}건"
                html_body = _build_html(cards, len(articles), base_url)
                _send_api(to_email, subject, html_body)
                results[i] = True
            except Exception as e:
                print(f"[EMAIL] 뉴스레터 발송 실패 {item.get('email')}: {e}")

        # HTTPS API는 요청마다 독립이라 동시에 보내도 된다 (한 통씩 기다리지 않음)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for i, item in enumerate(items):
                pool.submit(_one, i, item)
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
                    subject = f"[News Delivery] {cat_label} 최신 뉴스 {len(articles)}건"
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
    <h1 style="color:white;font-size:20px;font-weight:900;margin:0;">News Delivery</h1>
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
      이메일 인증하기
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
    if _api_provider():
        _send_api(to_email, subject, html_body)
        print(f"[EMAIL] {_api_provider()} 발송 성공: {to_email}")
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


def send_verify_email_async(to_email: str, token: str, base_url: str) -> None:
    """인증 메일을 백그라운드로 보낸다. 사용자가 발송 완료까지 기다리지 않게 하기 위함."""
    def _job():
        try:
            send_verify_email(to_email, token, base_url=base_url)
        except Exception as e:
            print(f"[EMAIL] 인증 메일 발송 실패: {e}")
    threading.Thread(target=_job, daemon=True).start()


# ── 계정 안내 메일 (아이디 찾기 · 비밀번호 재설정) ─────────────────────────
def _account_html(title: str, body_html: str, button_text: str | None = None, button_url: str | None = None) -> str:
    button = ""
    if button_text and button_url:
        button = f"""<a href="{button_url}"
       style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#cc0000,#ff4444);
              color:white;text-decoration:none;border-radius:24px;font-weight:700;font-size:15px;
              box-shadow:0 4px 12px rgba(204,0,0,0.3);">{button_text}</a>"""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:480px;margin:0 auto;padding:32px 16px;">
  <div style="background:linear-gradient(135deg,#cc0000,#ff4444);border-radius:12px 12px 0 0;padding:24px 28px;">
    <h1 style="color:white;font-size:20px;font-weight:900;margin:0;">News Delivery</h1>
  </div>
  <div style="background:white;padding:32px 28px;border-radius:0 0 12px 12px;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
    <h2 style="font-size:19px;color:#1a1a1a;margin:0 0 12px;">{title}</h2>
    <div style="font-size:15px;color:#555;line-height:1.8;margin:0 0 24px;">{body_html}</div>
    {button}
    <p style="font-size:12px;color:#adb5bd;margin:20px 0 0;">
      이 메일을 요청하지 않으셨다면 무시하셔도 됩니다. 계정은 그대로 안전합니다.
    </p>
  </div>
  <p style="text-align:center;font-size:12px;color:#adb5bd;margin-top:16px;">© 2026 News Delivery</p>
</div>
</body>
</html>"""


def send_html_email(to_email: str, subject: str, html_body: str) -> None:
    """HTML 메일 한 통 발송 (Brevo/SendGrid API 우선, 없으면 SMTP)."""
    if _api_provider():
        _send_api(to_email, subject, html_body)
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())


def send_account_email_async(to_email: str, subject: str, title: str, body_html: str,
                             button_text: str | None = None, button_url: str | None = None) -> None:
    html_body = _account_html(title, body_html, button_text, button_url)

    def _job():
        try:
            send_html_email(to_email, subject, html_body)
            print(f"[EMAIL] 계정 안내 메일 발송: {to_email}")
        except Exception as e:
            print(f"[EMAIL] 계정 안내 메일 실패 {to_email}: {e}")
    threading.Thread(target=_job, daemon=True).start()
