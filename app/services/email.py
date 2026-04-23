import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.naver.com"
SMTP_PORT = 587
SMTP_USER = "zestoper@naver.com"
SMTP_PASSWORD = "YVT68P7YPTJV"


def send_newsletter(
    to_emails: list[str],
    title: str,
    content: str,
    source: str = "",
    category_name: str = "",
    image_url: str = "",
    article_link: str = "",
    news_id: int = None,
    base_url: str = "http://127.0.0.1:8000",
) -> int:
    if not to_emails:
        return 0

    detail_url = f"{base_url.rstrip('/')}/news/{news_id}" if news_id else ""
    original_url = article_link or detail_url

    image_block = (
        f'<img src="{image_url}" alt="{title}" '
        f'style="width:100%; max-height:360px; object-fit:cover; display:block; border-radius:6px; margin-bottom:24px;">'
        if image_url else ""
    )
    link_block = (
        f'<div style="margin-top:28px; text-align:center;">'
        f'<a href="{original_url}" style="display:inline-block; padding:12px 28px; background:#c00; '
        f'color:white; text-decoration:none; border-radius:6px; font-size:14px; font-weight:700;">원문 보기</a>'
        f'</div>'
        if original_url else ""
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        sent_count = 0
        for email in to_emails:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[News Delivery] {category_name} - {title}"
            msg["From"] = SMTP_USER
            msg["To"] = email

            html_body = f"""
            <div style="max-width:600px; margin:0 auto; font-family:sans-serif;">
              <div style="background:#c00; padding:20px 24px;">
                <h1 style="color:white; margin:0; font-size:18px;">📰 News Delivery</h1>
                {'<span style="background:rgba(255,255,255,0.25); color:white; padding:2px 10px; border-radius:20px; font-size:12px; margin-left:10px;">' + category_name + '</span>' if category_name else ''}
              </div>
              <div style="padding:32px 24px; background:white;">
                <p style="font-size:12px; color:#868e96; margin-bottom:8px;">{source or '출처 없음'}</p>
                <h2 style="font-size:22px; color:#212529; margin-bottom:16px; line-height:1.4;">{title}</h2>
                <hr style="border:none; border-top:1px solid #e9ecef; margin-bottom:24px;">
                {image_block}
                <p style="font-size:15px; line-height:1.9; color:#333; white-space:pre-line;">{content}</p>
                {link_block}
              </div>
              <div style="padding:16px 24px; background:#f8f9fa; text-align:center;">
                <p style="font-size:12px; color:#adb5bd;">© 2026 News Delivery</p>
              </div>
            </div>
            """
            msg.attach(MIMEText(html_body, "html"))
            server.sendmail(SMTP_USER, email, msg.as_string())
            sent_count += 1

    return sent_count


def send_verify_email(to_email: str, token: str, base_url: str = "http://127.0.0.1:8000") -> None:
    verify_url = f"{base_url.rstrip('/')}/verify-email?token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[News Delivery] 이메일 인증을 완료해주세요"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    html_body = f"""
    <div style="max-width:600px; margin:0 auto; font-family:sans-serif;">
      <div style="background:#c00; padding:20px 24px;">
        <h1 style="color:white; margin:0; font-size:18px;">📰 News Delivery</h1>
      </div>
      <div style="padding:32px 24px; background:white;">
        <h2 style="font-size:20px; color:#1a1a1a; margin-bottom:16px;">이메일 인증</h2>
        <p style="font-size:15px; color:#555; line-height:1.8; margin-bottom:24px;">
          아래 버튼을 클릭하여 이메일 인증을 완료해주세요.
        </p>
        <a href="{verify_url}"
           style="display:inline-block; padding:14px 28px; background:#c00; color:white;
                  text-decoration:none; border-radius:6px; font-weight:700; font-size:15px;">
          이메일 인증하기
        </a>
      </div>
      <div style="padding:16px 24px; background:#f8f9fa; text-align:center;">
        <p style="font-size:12px; color:#adb5bd;">© 2026 News Delivery</p>
      </div>
    </div>
    """
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())