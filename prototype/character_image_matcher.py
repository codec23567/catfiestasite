# 사용 안 함: series_image_matcher.py 로 통합됨
import os
import re
from urllib.parse import unquote, urlparse
import character_crawler as cc
import github_image_extractor as gie
# ============================================================
# 설정
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
# battlecats ID: "072-1" -> (유닛번호, 폼번호)
CHARACTER_ID_PATTERN = re.compile(r"^(\d+)-(\d+)$")
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
    image_paths = gie.list_repo_images(
        GITHUB_OWNER, GITHUB_REPO, GITHUB_REF, GITHUB_PATH
    )
    if not image_paths:
        return {}
    index = {}
    for image_path in image_paths:
        folder = os.path.dirname(image_path)
        folder_name = folder.rsplit("/", 1)[-1]
        basename = os.path.basename(image_path)
        if not folder_name.isdigit():
            continue
        match = gie.NUMBERED_PNG_PATTERN.match(basename)
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
# battlecats ID "072-1"의 유닛번호(072)는 깃허브 폴더번호보다 1 크고,
# 폼번호(1)는 폴더 안의 png번호보다 1 크다.
# 예: "073-1" -> 깃허브 img/u/72/0.png
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
    source = cc.crawl_html(url)
    if source is None:
        return series_name, []
    _, records = cc.extract_character_ids(source)
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
    print("시리즈별 캐릭터-이미지 매칭기")
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
