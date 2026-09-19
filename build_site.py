"""
series_image_matcher.py 의 결과로 index.html 과 categories/*.html 을 만든다.

사용법
    python3 build_site.py                       # 나무위키/깃허브를 크롤링해서 바로 생성
    python3 build_site.py 결과.txt              # 이미 만들어 둔 결과 txt로 생성 (크롤링 생략)

타일 순서와 "어느 시리즈를 어느 페이지에 넣을지"는 아래 PAGES 에서만 관리한다.
"""

import html
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 페이지 정의 (이 순서대로 메인 화면에 타일이 나열된다)
#   slug   : categories/<slug>.html
#   label  : 메인 타일에 표시되는 이름 (= 페이지 제목)
#   groups : [(소제목 또는 None, 결과의 시리즈 이름), ...]  비어 있으면 "준비 중"
# ============================================================

PAGES = [
    ("dynamites", "다군", [(None, "다이너마이트 군단")]),
    ("basarazu", "바사", [(None, "초환수 바사라즈")]),
    ("galaxy_girls", "갤걸", [(None, "사이버 학원 갤럭시 걸즈")]),
    ("dragon_emperors", "드엠", [(None, "초파괴 대제 드래곤 엠퍼러스")]),
    ("ultra_souls", "울소", [(None, "초고대 전설의 용사 울트라 소울즈")]),
    ("dark_heroes", "닼히", [(None, "진격의 영웅 다크 히어로즈")]),
    ("gods", "갓즈", [(None, "궁극강림 기간트 제우스")]),
    ("iron_wars", "아워즈", [(None, "강철군대 아이언워즈")]),
    ("pixies", "픽시즈", [(None, "대정령 엘레멘탈 픽시즈")]),
    ("girls_monsters", "걸몬", [(None, "절명 미소녀 걸즈 몬스터즈")]),
    ("luga_family", "루가", [(None, "전설의 고양이 루가족")]),
    ("busters_fiesta", "바스인축", [
        ("바스터즈", "바스터즈(냥코 대전쟁)"),
        ("축제", "축제(냥코 대전쟁)"),
    ]),
    ("season", "계절", [(None, "냥코 대전쟁 / 캐릭터 / 울트라 슈퍼 레어 / 계절 한정")]),
    ("cat_fiesta", "고축", [(None, "고양이 축제")]),
    ("legend", "레레", []),
    ("collaboration", "콜라보", []),
]

# 섹션 번호로 캐릭터를 짝지어 나란히 놓는 페이지
# (고축: 나무위키의 2.1.1 요수 가오 <-> 3.1.1 흑수 가오우 처럼 최상위 번호를 뺀 나머지가 같으면 짝)
PAIRED_PAGES = {"cat_fiesta"}

# 페이지별로 맨 뒤에 놓을 캐릭터 (소제목으로 나뉜 페이지는 각 묶음의 맨 뒤)
MOVE_TO_END = {
    "busters_fiesta": ["고양이 왕자"],
}

# ============================================================
# 결과 읽기
# ============================================================

IMG_SRC_PATTERN = re.compile(r'<img\s+src="([^"]+)"')


def load_from_txt(path):
    """결과 txt -> {시리즈 이름: [(캐릭터 이름, ID, img 태그, 섹션 번호), ...]}"""
    series = {}
    current = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if not line:
                continue

            header = re.fullmatch(r"\[(.*)\]", line)
            if header:
                current = header.group(1)
                series[current] = []
                continue

            # 이름 : ID : img 태그 [: 섹션 번호]  (섹션 번호가 없는 예전 결과도 읽는다)
            parts = line.split(" : ")
            name, char_id, tag = parts[0], parts[1], parts[2]
            section = parts[3] if len(parts) > 3 else ""
            series[current].append((name, char_id, tag, section))

    return series


def load_from_crawl():
    """series_image_matcher 를 그대로 실행해서 결과를 얻는다."""
    sys.path.insert(0, BASE_DIR)
    import series_image_matcher as sim

    image_index = sim.build_github_image_index()
    series = {}

    for url in sim.NAMU_URLS:
        name, rows = sim.process_series(url, image_index)
        series[name] = rows

    return series


# ============================================================
# HTML 생성
# ============================================================

FONT = '-apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif'

INDEX_CSS = f"""  body {{
    margin: 0;
    font-family: {FONT};
    background: #111318;
    color: #eaeaf0;
    min-height: 100vh;
  }}
  header {{
    padding: 18px 20px;
    border-bottom: 1px solid #2a2d36;
  }}
  .home-btn {{
    color: #eaeaf0;
    text-decoration: none;
    font-weight: bold;
    font-size: 1.2rem;
  }}
  main {{
    max-width: 900px;
    margin: 0 auto;
    padding: 24px 16px 60px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }}
  .tile {{
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1.2 / 1;
    background: #000;
    color: #fff;
    text-decoration: none;
    font-weight: bold;
    font-size: 1rem;
    border: 1px solid #2a2d36;
    border-radius: 10px;
    text-align: center;
    padding: 8px;
  }}
  .tile:hover {{
    background: #1a1a1a;
    border-color: #4a4d56;
  }}
  @media (max-width: 480px) {{
    .grid {{
      grid-template-columns: repeat(2, 1fr);
    }}
  }}"""

CATEGORY_CSS = f"""  body {{
    margin: 0;
    font-family: {FONT};
    background: #111318;
    color: #eaeaf0;
    min-height: 100vh;
  }}
  header {{
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 20px;
    border-bottom: 1px solid #2a2d36;
  }}
  .home-btn {{
    color: #eaeaf0;
    text-decoration: none;
    font-weight: bold;
    font-size: 1.1rem;
    padding: 6px 12px;
    border: 1px solid #3a3d46;
    border-radius: 8px;
  }}
  .home-btn:hover {{
    background: #1c1f27;
  }}
  header h1 {{
    margin: 0;
    font-size: 1.2rem;
    color: #cfd2e0;
  }}
  main {{
    max-width: 900px;
    margin: 0 auto;
    padding: 24px 16px 60px;
  }}
  main.empty {{
    max-width: 700px;
    padding: 40px 20px;
    text-align: center;
  }}
  main p {{
    color: #9a9db0;
    line-height: 1.6;
  }}
  h2 {{
    margin: 32px 0 12px;
    font-size: 1.1rem;
    color: #cfd2e0;
    border-bottom: 1px solid #2a2d36;
    padding-bottom: 6px;
  }}
  h2:first-child {{
    margin-top: 0;
  }}
  .chars {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }}
  .card {{
    background: #1a1d24;
    border: 1px solid #2a2d36;
    border-radius: 10px;
    padding: 10px;
    text-align: center;
  }}
  .card .name {{
    font-size: 0.85rem;
    font-weight: bold;
    color: #eaeaf0;
    margin-bottom: 8px;
    word-break: keep-all;
  }}
  .forms {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 3px;
  }}
  .forms img {{
    width: 64px;
    height: auto;
  }}
  main.wide {{
    max-width: 1100px;
  }}
  .pairs {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 400px), 1fr));
    gap: 12px;
  }}
  .pair {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 6px;
    background: #15181e;
    border-radius: 12px;
  }}
  @media (max-width: 560px) {{
    .pair {{
      grid-template-columns: 1fr;
    }}
  }}"""


def esc(text):
    return html.escape(text, quote=True)


def page(title, css, body, lang_title=None):
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<style>
{css}
</style>
</head>
<body>

{body}

</body>
</html>
"""


def build_index():
    tiles = "\n".join(
        f'    <a class="tile" href="categories/{slug}.html">{esc(label)}</a>'
        for slug, label, _ in PAGES
    )

    body = f"""<header>
  <a class="home-btn" href="index.html">catfiesta</a>
</header>

<main>
  <div class="grid">
{tiles}
  </div>
</main>"""

    return page("catfiesta", INDEX_CSS, body)


def group_characters(rows):
    """같은 이름의 캐릭터를 묶어서 [(이름, [이미지 주소, ...], 섹션 번호), ...] (나온 순서 유지)"""
    grouped = {}

    for name, _char_id, tag, section in rows:
        match = IMG_SRC_PATTERN.search(tag)

        if not match:
            continue

        urls, _ = grouped.setdefault(name, ([], section))
        urls.append(match.group(1))

    return [(name, urls, section) for name, (urls, section) in grouped.items()]


def section_key(text):
    return [int(part) for part in text.split(".")]


def pair_characters(characters):
    """
    섹션 번호로 짝을 맞춘다.
    최상위 번호가 다른 두 묶음(예: 2.1.1 과 3.1.1)에서 최상위 번호를 뺀 나머지(1.1)가
    같은 캐릭터끼리 짝이다. -> [(왼쪽 캐릭터 또는 None, 오른쪽 캐릭터 또는 None), ...]
    묶음이 정확히 둘이 아니거나 섹션 번호가 없으면 None.
    """
    by_top = {}

    for name, urls, section in characters:
        if not section:
            return None

        top, _, rest = section.partition(".")
        by_top.setdefault(top, {})[rest] = (name, urls)

    if len(by_top) != 2:
        return None

    left_top, right_top = sorted(by_top, key=int)
    left, right = by_top[left_top], by_top[right_top]

    rows = []

    for rest in sorted(set(left) | set(right), key=section_key):
        left_side, right_side = left.get(rest), right.get(rest)
        rows.append((left_side, right_side))

        if left_side is None:
            print(f"[경고] {left_top}.{rest} 에 대응하는 캐릭터가 없어 "
                  f"'{right_side[0]}'({right_top}.{rest})을 짝 없이 표시합니다")
        elif right_side is None:
            print(f"[경고] {right_top}.{rest} 에 대응하는 캐릭터가 없어 "
                  f"'{left_side[0]}'({left_top}.{rest})을 짝 없이 표시합니다")

    return rows


def render_card(name, urls, indent="    "):
    imgs = "\n".join(
        f'{indent}    <img src="{esc(url)}" alt="{esc(name)}" loading="lazy">'
        for url in urls
    )

    return (
        f'{indent}<div class="card">\n'
        f'{indent}  <div class="name">{esc(name)}</div>\n'
        f'{indent}  <div class="forms">\n{imgs}\n{indent}  </div>\n'
        f'{indent}</div>'
    )


def render_characters(rows, paired=False, last=()):
    characters = group_characters(rows)

    # last 에 적은 캐릭터는 (그 묶음 안에서) 맨 뒤로 보낸다. 적은 순서대로 뒤에 붙는다.
    if last:
        moved = [c for name in last for c in characters if c[0] == name]
        characters = [c for c in characters if c[0] not in last] + moved

    if paired:
        pair_rows = pair_characters(characters)

        if pair_rows is None:
            print("[경고] 섹션 번호로 짝을 맞추지 못해 일반 배치로 표시합니다")
        else:
            units = []

            for left_side, right_side in pair_rows:
                slots = [
                    render_card(*side, "      ") if side else '      <div class="slot"></div>'
                    for side in (left_side, right_side)
                ]
                units.append('    <div class="pair">\n' + "\n".join(slots) + "\n    </div>")

            return '  <div class="pairs">\n' + "\n".join(units) + "\n  </div>"

    cards = [render_card(name, urls) for name, urls, _section in characters]

    return '  <div class="chars">\n' + "\n".join(cards) + "\n  </div>"


def build_category(label, groups, series, paired=False, last=()):
    sections = []

    all_names = {row[0] for _, series_name in groups for row in series.get(series_name, [])}
    for name in last:
        if name not in all_names:
            print(f"[경고] 맨 뒤로 보낼 캐릭터 '{name}' 이(가) {label} 결과에 없습니다")

    for subtitle, series_name in groups:
        rows = series.get(series_name, [])

        if not rows:
            print(f"[경고] '{series_name}' 결과가 없습니다 ({label})")
            continue

        heading = f"  <h2>{esc(subtitle)}</h2>\n" if subtitle else ""
        sections.append(heading + render_characters(rows, paired, last))

    if sections:
        main_class = ' class="wide"' if paired else ""
        main = f'<main{main_class}>\n' + "\n\n".join(sections) + "\n</main>"
    else:
        main = f"""<main class="empty">
  <p>"{esc(label)}" 카테고리 목록이 여기에 들어갈 예정입니다.</p>
  <p>(내용 준비 중)</p>
</main>"""

    body = f"""<header>
  <a class="home-btn" href="../index.html">◀ catfiesta</a>
  <h1>{esc(label)}</h1>
</header>

{main}"""

    return page(f"{label} - catfiesta", CATEGORY_CSS, body)


def write(path, text):
    with open(os.path.join(BASE_DIR, path), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    if len(sys.argv) > 1:
        series = load_from_txt(sys.argv[1])
    else:
        series = load_from_crawl()

    os.makedirs(os.path.join(BASE_DIR, "categories"), exist_ok=True)

    write("index.html", build_index())

    for slug, label, groups in PAGES:
        write(
            f"categories/{slug}.html",
            build_category(
                label, groups, series,
                paired=slug in PAIRED_PAGES,
                last=MOVE_TO_END.get(slug, ()),
            ),
        )

    used = {name for _, _, groups in PAGES for _, name in groups}
    for name in series:
        if name not in used:
            print(f"[경고] 어느 페이지에도 넣지 않은 시리즈: {name}")

    print(f"[완료] index.html + categories/*.html {len(PAGES)}개")


if __name__ == "__main__":
    main()
