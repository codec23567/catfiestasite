# 사용 안 함: series_image_matcher.py 로 통합됨
import os
import re
import time
from urllib.parse import urlparse
import requests
# ============================================================
# 설정
# ============================================================
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".svg", ".bmp", ".ico",
}
DEFAULT_REPO_URL = "https://github.com/shadowgao42/nyankodb/tree/main/img/u"
# https://github.com/owner/repo
# https://github.com/owner/repo/tree/branch/path...
# owner/repo
REPO_URL_PATTERN = re.compile(
    r"^(?:https?://github\.com/)?"
    r"(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?"
    r"(?:/tree/(?P<ref>[^/\s]+)(?:/(?P<path>.+))?)?"
    r"/?$"
)
# 폴더 안에서 "숫자.png" 형태의 파일만 매칭 (예: 0.png, 12.png)
# a, c0.png 같은 파일은 매칭하지 않음
NUMBERED_PNG_PATTERN = re.compile(r"^(\d+)\.png$", re.IGNORECASE)
def _auth_headers():
    headers = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers
# ============================================================
# URL 파싱
# ============================================================
def parse_repo_url(url):
    url = url.strip()
    match = REPO_URL_PATTERN.match(url)
    if not match:
        return None
    return {
        "owner": match.group("owner"),
        "repo": match.group("repo"),
        "ref": match.group("ref"),
        "path": match.group("path") or "",
    }
# ============================================================
# 기본 브랜치 조회
# ============================================================
def get_default_branch(owner, repo):
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    print(f"[요청] {api_url}")
    response = requests.get(
        api_url,
        headers=_auth_headers(),
        timeout=TIMEOUT,
    )
    if response.status_code == 404:
        print(f"[오류] 저장소를 찾을 수 없습니다: {owner}/{repo}")
        return None
    if response.status_code == 403:
        print(
            "[오류] GitHub API 레이트리밋에 도달한 것으로 보입니다. "
            "GITHUB_TOKEN 환경변수를 설정하면 완화됩니다."
        )
        return None
    response.raise_for_status()
    return response.json().get("default_branch")
# ============================================================
# 이미지 목록 조회
# ============================================================
def list_repo_images(owner, repo, ref, path):
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/git/trees/{ref}?recursive=1"
    )
    print(f"[요청] {api_url}")
    start_time = time.time()
    response = requests.get(
        api_url,
        headers=_auth_headers(),
        timeout=TIMEOUT,
    )
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
# 폴더별 최대 숫자.png 선택
# ============================================================
def select_largest_numbered_png_per_folder(image_paths):
    """
    같은 폴더 안에 0.png, 1.png, 2.png 처럼 "숫자.png" 파일이
    여러 개 있을 때, 폴더별로 숫자가 가장 큰 파일 하나만 남긴다.
    "a", "c0.png" 처럼 패턴에 안 맞는 파일은 대상에서 제외된다.
    """
    best_by_folder = {}
    for image_path in image_paths:
        folder = os.path.dirname(image_path)
        basename = os.path.basename(image_path)
        match = NUMBERED_PNG_PATTERN.match(basename)
        if not match:
            continue
        number = int(match.group(1))
        current = best_by_folder.get(folder)
        if current is None or number > current[0]:
            best_by_folder[folder] = (number, image_path)
    def sort_key(folder):
        last_segment = folder.rsplit("/", 1)[-1]
        if last_segment.isdigit():
            return (0, int(last_segment), folder)
        return (1, 0, folder)
    selected_paths = [
        best_by_folder[folder][1]
        for folder in sorted(best_by_folder, key=sort_key)
    ]
    print(
        f"[결과] 폴더별 최대 숫자.png 선택 : "
        f"{len(best_by_folder)}개 폴더 → {len(selected_paths)}개 파일"
    )
    return selected_paths
# ============================================================
# <img> 태그 생성
# ============================================================
def build_img_tags(owner, repo, ref, image_paths):
    img_tags = []
    for image_path in image_paths:
        raw_url = (
            f"https://raw.githubusercontent.com/"
            f"{owner}/{repo}/{ref}/{image_path}"
        )
        img_tags.append(f'<img src="{raw_url}">')
    return img_tags
# ============================================================
# 결과 저장
# ============================================================
def save_folder_img_map(repo, image_paths, img_tags):
    """
    각 줄을 "폴더명 : <img 태그>" 형태로 저장한다.
    실행할 때마다 같은 파일명으로 덮어써서 최신 결과로 갱신된다.
    """
    entries = list(zip(image_paths, img_tags))
    def sort_key(item):
        folder = os.path.dirname(item[0])
        last_segment = folder.rsplit("/", 1)[-1]
        if last_segment.isdigit():
            return (0, int(last_segment), folder)
        return (1, 0, folder)
    entries.sort(key=sort_key)
    filename = f"{repo}_folder_images.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for image_path, tag in entries:
            folder = os.path.dirname(image_path).rsplit("/", 1)[-1]
            f.write(f"{folder} : {tag}\n")
    print(f"[저장] {filename} ({len(entries)}줄)")
    return filename
# ============================================================
# 실행
# ============================================================
def main():
    print("=" * 80)
    print("GitHub 저장소 이미지 <img> 태그 추출기")
    print("=" * 80)
    url = DEFAULT_REPO_URL
    parsed = parse_repo_url(url)
    if not parsed:
        print("[오류] GitHub 저장소 URL 형식을 인식하지 못했습니다.")
        return
    owner = parsed["owner"]
    repo = parsed["repo"]
    ref = parsed["ref"]
    path = parsed["path"]
    if not ref:
        ref = get_default_branch(owner, repo)
        if not ref:
            return
    print()
    print(f"[대상] {owner}/{repo}@{ref}" + (f" ({path})" if path else ""))
    print()
    image_paths = list_repo_images(owner, repo, ref, path)
    if image_paths is None:
        return
    if not image_paths:
        print("[완료] 이미지를 찾지 못했습니다.")
        return
    image_paths = select_largest_numbered_png_per_folder(image_paths)
    if not image_paths:
        print("[완료] 숫자.png 패턴에 맞는 파일을 찾지 못했습니다.")
        return
    img_tags = build_img_tags(owner, repo, ref, image_paths)
    print()
    save_folder_img_map(repo, image_paths, img_tags)
if __name__ == "__main__":
    main()
