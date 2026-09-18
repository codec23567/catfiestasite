import html
import os
import re
import time
from urllib.parse import unquote, urlparse

import requests

# ============================================================
# 공통 설정
# ============================================================
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
TARGET_DOMAIN = "battlecats-db.com"
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".svg", ".bmp", ".ico",
}

# 나무위키 목차/본문 파싱용 정규식 (character_crawler.py)
TOC_PATTERN = re.compile(
    r'<a\b[^>]*href=["\']#s-(\d+(?:\.\d+)+)["\'][^>]*>.*?</a>'
    r'(.*?)</span>',
    re.IGNORECASE | re.DOTALL
)
SECTION_PATTERN = re.compile(
    r'<a\b[^>]*id=["\']s-(\d+(?:\.\d+)+)["\'][^>]*>',
    re.IGNORECASE
)
BATTLECATS_LINK_PATTERN = re.compile(
    r'<a\b[^>]*href=["\']'
    r'(https?://(?:www\.)?battlecats-db\.com/[^"\']*)'
    r'["\'][^>]*>'
    r'(.*?)</a>',
    re.IGNORECASE | re.DOTALL
)
ID_PATTERN = re.compile(r"^\d+-\d+$")

# GitHub 이미지 파싱용 정규식 (github_image_extractor.py)
NUMBERED_PNG_PATTERN = re.compile(r"^(\d+)\.png$", re.IGNORECASE)

# ============================================================
# 매칭기 자체 설정
# ============================================================
NAMU_URLS = [
    "https://namu.wiki/w/%EB%8B%A4%EC%9D%B4%EB%84%88%EB%A7%88%EC%9D%B4%ED%8A%B8%20%EA%B5%B0%EB%8B%A8",
    "https://namu.wiki/w/%EC%B4%88%ED%99%98%EC%88%98%20%EB%B0%94%EC%82%AC%EB%9D%BC%EC%A6%88",
    "https://namu.wiki/w/%EC%82%AC%EC%9D%B4%EB%B2%84%20%ED%95%99%EC%9B%90%20%EA%B0%A4%EB%9F%AD%EC%8B%9C%20%EA%B1%B8%EC%A6%88",
    "https://namu.wiki/w/%EC%B4%88%ED%8C%8C%EA%B4%B4%20%EB%8C%80%EC%A0%9C%20%EB%93%9C%EB%9E%98%EA%B3%A4%20%EC%97%A0%ED%8D%BC%EB%9F%AC%EC%8A%A4",
    "https://namu.wiki/w/%EC%B4%88%EA%B3%A0%EB%8C%80%20%EC%A0%84%EC%84%A4%EC%9D%98%20%EC%9A%A9%EC%82%AC%20%EC%9A%B8%ED%8A%B8%EB%9D%BC%20%EC%86%8C%EC%9A%B8%EC%A6%88",
    "https://namu.wiki/w/%EC%A7%84%EA%B2%A9%EC%9D%98%20%EC%98%81%EC%9B%85%20%EB%8B%A4%ED%81%AC%20%ED%9E%88%EC%96%B4%EB%A1%9C%EC%A6%88",
    "https://namu.wiki/w/%EA%B6%81%EA%B7%B9%EA%B0%95%EB%A6%BC%20%EA%B8%B0%EA%B0%84%ED%8A%B8%20%EC%A0%9C%EC%9A%B0%EC%8A%A4",
    "https://namu.wiki/w/%EA%B0%95%EC%B2%A0%EA%B5%B0%EB%8C%80%20%EC%95%84%EC%9D%B4%EC%96%B8%EC%9B%8C%EC%A6%88",
    "https://namu.wiki/w/%EB%8C%80%EC%A0%95%EB%A0%B9%20%EC%97%98%EB%A0%88%EB%A9%98%ED%83%88%20%ED%94%BD%EC%8B%9C%EC%A6%88",
    "https://namu.wiki/w/%EC%A0%88%EB%AA%85%20%EB%AF%B8%EC%86%8C%EB%85%80%20%EA%B1%B8%EC%A6%88%20%EB%AA%AC%EC%8A%A4%ED%84%B0%EC%A6%88",
    "https://namu.wiki/w/%EC%A0%84%EC%84%A4%EC%9D%98%20%EA%B3%A0%EC%96%91%EC%9D%B4%20%EB%A3%A8%EA%B0%80%EC%A1%B1",
    "https://namu.wiki/w/%EC%B6%95%EC%A0%9C(%EB%83%A5%EC%BD%94%20%EB%8C%80%EC%A0%84%EC%9F%81)",
    "https://namu.wiki/w/%EB%B0%94%EC%8A%A4%ED%84%B0%EC%A6%88(%EB%83%A5%EC%BD%94%20%EB%8C%80%EC%A0%84%EC%9F%81)",
    "https://namu.wiki/w/%EB%83%A5%EC%BD%94%20%EB%8C%80%EC%A0%84%EC%9F%81/%EC%BA%90%EB%A6%AD%ED%84%B0/%EC%9A%B8%ED%8A%B8%EB%9D%BC%20%EC%8A%88%ED%8D%BC%20%EB%A0%88%EC%96%B4/%EA%B3%84%EC%A0%88%20%ED%95%9C%EC%A0%95",
    "https://namu.wiki/w/%EA%B3%A0%EC%96%91%EC%9D%B4%20%EC%B6%95%EC%A0%9C",
]
GITHUB_OWNER = "shadowgao42"
GITHUB_REPO = "nyankodb"
GITHUB_REF = "main"
GITHUB_PATH = "img/u"
CHARACTER_ID_PATTERN = re.compile(r"^(\d+)-(\d+)$")


# ============================================================
# 텍스트 처리
# ============================================================
def strip_tags(text):
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def normalize_text(text):
    text = strip_tags(text)
    return re.sub(r"\s+", " ", text).strip()


def is_namu_url(url):
    try:
        host = urlparse(url).netloc.lower()
        return host == "namu.wiki" or host.endswith(".namu.wiki")
    except Exception:
        return False


# ============================================================
# 나무위키 HTML 크롤링
# ============================================================
def crawl_html(url):
    print()
    print("=" * 80)
    print("HTML 크롤링")
    print("=" * 80)
    print(f"[요청] {url}")
    start_time = time.time()
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        request_time = time.time() - start_time
        print(
            f"[응답] 상태={response.status_code}, "
            f"바이트={len(response.content):,}, "
            f"인코딩={response.encoding}"
        )
        print(f"[응답] Content-Type={response.headers.get('Content-Type', '')}")
        print(f"[응답] 최종 URL={response.url}")
        print(f"[시간] HTTP 요청 : {request_time:.2f}초")
        response.raise_for_status()
        if response.content.startswith(b"\xef\xbb\xbf"):
            source = response.content.decode("utf-8-sig")
        else:
            source = response.content.decode("utf-8", errors="replace")
        return source
    except requests.Timeout:
        print("[오류] HTTP 요청 시간 초과")
        return None
    except requests.RequestException as e:
        print(f"[오류] HTTP 요청 실패: {e}")
        return None
    except Exception as e:
        print(f"[오류] 크롤링 실패: {e}")
        return None


# ============================================================
# 목차 캐릭터 추출
# ============================================================
def extract_toc_characters(source):
    characters = []
    seen = set()
    for match in TOC_PATTERN.finditer(source):
        section = match.group(1)
        raw_name = match.group(2)
        name = normalize_text(raw_name)
        name = re.sub(r"^\s*\d+(?:\.\d+)+\.?\s*", "", name).strip()
        name = re.sub(r"^[\s.]+", "", name).strip()
        if not name:
            continue
        if section in seen:
            continue
        seen.add(section)
        characters.append({"section": section, "name": name})
    return characters


def extract_section_positions(source):
    positions = {}
    for match in SECTION_PATTERN.finditer(source):
        section = match.group(1)
        if section not in positions:
            positions[section] = match.start()
    return positions


def extract_battlecats_links(section_source):
    results = []
    for match in BATTLECATS_LINK_PATTERN.finditer(section_source):
        url = html.unescape(match.group(1))
        link_text = normalize_text(match.group(2))
        if not ID_PATTERN.fullmatch(link_text):
            continue
        results.append({"id": link_text, "url": url})
    return results


def extract_character_ids(source):
    characters = extract_toc_characters(source)
    section_positions = extract_section_positions(source)
    print()
    print(f"[목차] 캐릭터 목록 : {len(characters):,}개")
    records = []
    for index, character in enumerate(characters):
        section = character["section"]
        name = character["name"]
        start = section_positions.get(section)
        if start is None:
            print(f"[경고] 본문 섹션 없음: {section} {name}")
            continue
        end = len(source)
        for next_character in characters[index + 1:]:
            next_start = section_positions.get(next_character["section"])
            if next_start is not None and next_start > start:
                end = next_start
                break
        section_source = source[start:end]
        links = extract_battlecats_links(section_source)
        seen_ids = set()
        for link in links:
            key = (link["id"], link["url"])
            if key in seen_ids:
                continue
            seen_ids.add(key)
            records.append({"character_name": name, "id": link["id"]})
        print(f"[매칭] {section}. {name} → {len(seen_ids)}개 ID")
    return characters, records


# ============================================================
# GitHub 이미지 목록 조회
# ============================================================
def _auth_headers():
    headers = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def list_repo_images(owner, repo, ref, path):
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/git/trees/{ref}?recursive=1"
    )
    print(f"[요청] {api_url}")
    start_time = time.time()
    response = requests.get(api_url, headers=_auth_headers(), timeout=TIMEOUT)
    print(f"[시간] HTTP 요청 : {time.time() - start_time:.2f}초")
    if response.status_code == 404:
        print(f"[오류] 저장소 또는 브랜치를 찾을 수 없습니다: {owner}/{repo}@{ref}")
        return None
    if response.status_code == 403:
        print(
            "[오류] GitHub API 레이트리밋에 도달한 것으로 보입니다. "
            "GITHUB_TOKEN 환경변수를 설정하면 완화됩니다."
        )
        return None
    response.raise_for_status()
    data = response.json()
    if data.get("truncated"):
        print(
            "[경고] 저장소가 너무 커서 트리 결과가 일부 잘렸습니다. "
            "path를 좁혀서 다시 시도하세요."
        )
    tree = data.get("tree", [])
    normalized_path = path.strip("/")
    image_paths = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        entry_path = entry.get("path", "")
        if normalized_path and not (
            entry_path == normalized_path
            or entry_path.startswith(normalized_path + "/")
        ):
            continue
        _, ext = os.path.splitext(entry_path)
        if ext.lower() in IMAGE_EXTENSIONS:
            image_paths.append(entry_path)
    print(f"[결과] 이미지 파일 수 : {len(image_paths)}")
    return image_paths


# ============================================================
# 나무위키 URL -> 시리즈 이름
# ============================================================
def decode_series_name(url):
    path = urlparse(url).path
    if path.startswith("/w/"):
        path = path[len("/w/"):]
    segments = [unquote(segment) for segment in path.split("/") if segment]
    return " / ".join(segments)


# ============================================================
# 깃허브 이미지 인덱스: (폴더번호, png번호) -> 이미지 경로
# ============================================================
def build_github_image_index():
    print()
    print("=" * 80)
    print("깃허브 이미지 인덱스 구축")
    print("=" * 80)
    image_paths = list_repo_images(GITHUB_OWNER, GITHUB_REPO, GITHUB_REF, GITHUB_PATH)
    if not image_paths:
        return {}
    index = {}
    for image_path in image_paths:
        folder = os.path.dirname(image_path)
        folder_name = folder.rsplit("/", 1)[-1]
        basename = os.path.basename(image_path)
        if not folder_name.isdigit():
            continue
        match = NUMBERED_PNG_PATTERN.match(basename)
        if not match:
            continue
        index[(int(folder_name), int(match.group(1)))] = image_path
    print(f"[결과] 숫자.png 인덱스 : {len(index)}개")
    return index


def image_path_to_tag(image_path):
    raw_url = (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_REF}/{image_path}"
    )
    return f'<img src="{raw_url}">'


# ============================================================
# 아이디 <-> 이미지 매칭
# ============================================================
def match_id_to_tag(character_id, image_index):
    match = CHARACTER_ID_PATTERN.fullmatch(character_id)
    if not match:
        return None
    unit_num = int(match.group(1))
    form_num = int(match.group(2))
    folder_num = unit_num - 1
    png_num = form_num - 1
    image_path = image_index.get((folder_num, png_num))
    if image_path is None:
        return None
    return image_path_to_tag(image_path)


# ============================================================
# 시리즈 처리
# ============================================================
def process_series(url, image_index):
    series_name = decode_series_name(url)
    source = crawl_html(url)
    if source is None:
        return series_name, []
    _, records = extract_character_ids(source)
    rows = []
    for record in records:
        tag = match_id_to_tag(record["id"], image_index)
        rows.append((record["character_name"], record["id"], tag))
    return series_name, rows


# ============================================================
# 결과 저장
# ============================================================
def save_results(all_series):
    filename = "series_character_images.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for series_name, rows in all_series:
            f.write(f"[{series_name}]\n")
            for name, char_id, tag in rows:
                tag_text = tag if tag else "이미지 없음"
                f.write(f"{name} : {char_id} : {tag_text}\n")
            f.write("\n")
    print(f"[저장] {filename}")
    return filename


# ============================================================
# 실행
# ============================================================
def main():
    print("=" * 80)
    print("시리즈별 캐릭터-이미지 매칭기 (독립 실행형)")
    print("=" * 80)
    image_index = build_github_image_index()
    all_series = []
    for url in NAMU_URLS:
        series_name, rows = process_series(url, image_index)
        all_series.append((series_name, rows))
    print()
    save_results(all_series)


if __name__ == "__main__":
    main()
