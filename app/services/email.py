import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

SMTP_HOST = settings.SMTP_HOST
SMTP_PORT = settings.SMTP_PORT
SMTP_USER = settings.SMTP_USER
SMTP_PASSWORD = settings.SMTP_PASSWORD

_CAT_EMOJI = {
    "정치": "🏛", "경제": "💰", "IT": "💻", "문화": "🎭",
    "스포츠": "⚽", "예술": "🎨", "연예": "🎬", "국제": "🌐", "사회": "📋",
}


def _card_html(article: dict, base_url: str) -> str:
    news_id = article.get("id")
    title = article.get("title", "")
    source = article.get("source") or ""
    cat = article.get("category_name") or ""
    image_url = article.get("image_url") or ""
    content = article.get("content") or ""
    link = article.get("link") or (f"{base_url}/news/{news_id}" if news_id else "")

    excerpt = content.replace("\n", " ").strip()[:120]
    if len(content.replace("\n", " ").strip()) > 120:
        excerpt += "…"

    cat_emoji = _CAT_EMOJI.get(cat, "📰")
    cat_badge = (
        f'<span style="display:inline-block;background:#fff0f0;color:#c00;'
        f'font-size:11px;font-weight:700;padding:2px 9px;border-radius:12px;margin-bottom:10px;">'
        f'{cat_emoji} {cat}</span>' if cat else ""
    )

    image_block = (
        f'<img src="{image_url}" alt="{title}" '
        f'style="width:100%;height:180px;object-fit:cover;display:block;border-radius:6px 6px 0 0;">'
        if image_url and image_url.startswith("http") else ""
    )

    btn = (
        f'<a href="{link}" '
        f'style="display:inline-block;padding:9px 22px;background:#c00;color:white;'
        f'text-decoration:none;border-radius:20px;font-size:13px;font-weight:700;">기사 읽기 →</a>'
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
        <p style="font-size:14px;color:#555;line-height:1.75;margin:0 0 16px;">{excerpt}</p>
        {btn}
      </div>
    </div>"""


def send_newsletter(
    to_email: str,
    articles: list,
    base_url: str = "http://127.0.0.1:8000",
) -> bool:
    if not articles or not to_email:
        return False

    base_url = base_url.rstrip("/")
    cards = "".join(_card_html(a, base_url) for a in articles)

    cats = sorted({a.get("category_name") for a in articles if a.get("category_name")})
    subject_cats = " · ".join(cats) if cats else "뉴스"
    subject = f"[News Delivery] 오늘의 {subject_cats} 뉴스 {len(articles)}건"

    html_body = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;">

  <!-- 헤더 -->
  <div style="background:linear-gradient(135deg,#cc0000,#ff4444);border-radius:12px 12px 0 0;
              padding:24px 28px;margin-bottom:0;">
    <p style="color:rgba(255,255,255,0.75);font-size:11px;margin:0 0 4px;letter-spacing:1px;text-transform:uppercase;">News Delivery</p>
    <h1 style="color:white;font-size:22px;font-weight:900;margin:0;letter-spacing:-0.5px;">오늘의 뉴스레터</h1>
    <p style="color:rgba(255,255,255,0.8);font-size:13px;margin:6px 0 0;">
      구독하신 카테고리의 최신 뉴스 <strong style="color:white;">{len(articles)}건</strong>을 전달해드립니다.
    </p>
  </div>

  <!-- 구분선 -->
  <div style="height:4px;background:linear-gradient(90deg,#cc0000,#ff6b6b);margin-bottom:20px;"></div>

  <!-- 기사 카드 -->
  {cards}

  <!-- 푸터 -->
  <div style="text-align:center;padding:20px 0 8px;">
    <p style="font-size:13px;color:#868e96;margin:0 0 6px;">
      <a href="{base_url}" style="color:#c00;text-decoration:none;font-weight:700;">📰 News Delivery</a> 뉴스레터
    </p>
    <p style="font-size:12px;color:#adb5bd;margin:0;">
      © 2026 News Delivery ·
      <a href="{base_url}/subscribe" style="color:#adb5bd;">구독 설정 변경</a>
    </p>
  </div>

</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception:
        return False


def send_verify_email(to_email: str, token: str, base_url: str = "http://127.0.0.1:8000") -> None:
    verify_url = f"{base_url.rstrip('/')}/verify-email?token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[News Delivery] 이메일 인증을 완료해주세요"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

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

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
