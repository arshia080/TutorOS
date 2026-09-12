from app.services.upload_service import content_disposition


def test_content_disposition_normal_filename():
    header = content_disposition("homework.pdf")
    assert 'filename="homework.pdf"' in header


def test_content_disposition_strips_quotes_and_backslashes():
    header = content_disposition('evil".pdf')
    # The ASCII fallback must never contain an unescaped quote -- that would
    # let a malicious filename break out of the quoted header value.
    fallback = header.split(";")[1].strip()
    assert fallback.count('"') == 2  # exactly the two we added ourselves
    assert "\\" not in header


def test_content_disposition_rejects_crlf_injection():
    malicious = 'a.pdf"\r\nSet-Cookie: session=stolen'
    header = content_disposition(malicious)
    assert "\r" not in header
    assert "\n" not in header


def test_content_disposition_percent_encodes_non_ascii():
    header = content_disposition("résumé.pdf")
    assert "filename*=UTF-8''" in header
    assert "%C3%A9" in header  # percent-encoded é
