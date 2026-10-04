import pytest

from app.services.youtube import extract_video_id


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ?t=10",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://m.youtube.com/embed/dQw4w9WgXcQ",
])
def test_extract_video_id_ok(url):
    assert extract_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    "https://evil.com/watch?v=dQw4w9WgXcQ",
    "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/",
    "not a url",
])
def test_extract_video_id_rejects(url):
    with pytest.raises(ValueError):
        extract_video_id(url)


def test_youtube_endpoint_rejects_bad_url(client):
    r = client.post("/api/v1/analyses/youtube", json={"url": "https://evil.com/x", "mode": "llm"})
    assert r.status_code == 400
