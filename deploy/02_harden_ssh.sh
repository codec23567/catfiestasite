#!/usr/bin/env bash
# =====================================================================
# 보안 관련 정보 모음 + SSH 강화 스크립트
#
# 평소에는 이 파일을 쓸 일이 없다 (root 비밀번호 방식으로 운영).
# 보안이 걱정되는 상황이 오면 이 주석부터 읽는다. 보안 관련 내용은 README/CLAUDE.md 가 아니라 여기에 모아 둔다.
#
# ---------------------------------------------------------------------
# 1. 서버에 들어 있는 민감한 것 (서버가 뚫리면 넘어가는 것)
# ---------------------------------------------------------------------
#   .env 의 CAT_ID / CAT_PW      카페 계정. 그 계정으로 글을 쓰고 고칠 수 있다 (m_* 작업이 실제로 카페 글을 수정함)
#   .env 의 WEBHOOK_SECRET       웹훅 토큰. 시트 작업(J열, F/G열 덮어쓰기)을 임의로 실행할 수 있다
#   credentials.json             구글 서비스 계정 키. 그 계정에 공유된 모든 시트를 읽고 편집할 수 있다
#   ~/.ssh/catfiestasite_deploy  (push 용 배포 키를 만들었다면) catfiestasite 쓰기 권한.
#                                그 저장소는 GitHub Pages 공개 사이트라서 방문자에게 나가는 코드를 바꿀 수 있다
#   시트 안의 데이터             서비스 계정 키로 읽을 수 있다 (무엇이 들어 있는지는 이 저장소에서 확인하지 않음)
#
# ---------------------------------------------------------------------
# 2. 지금 적용되어 있는 보호 (01_bootstrap.sh)
# ---------------------------------------------------------------------
#   ufw          22, 5000 만 열림 (5000 은 구글 IP 를 특정할 수 없어 전체 공개, 인증은 WEBHOOK_SECRET 하나)
#   fail2ban     10분 안에 SSH 로그인 5회 실패 시 1시간 차단 (반복하면 점점 길어짐, 최대 1주)
#   파일 권한    .env, credentials.json 은 chmod 600
#   업데이트     unattended-upgrades 패키지 설치 (실제 자동 적용 여부는 서버에서 확인 필요)
#
# ---------------------------------------------------------------------
# 3. root 비밀번호 방식을 계속 쓸 때의 수칙
# ---------------------------------------------------------------------
#   - root 비밀번호는 길고 복잡하게, 다른 곳과 겹치지 않게 (짧으면 fail2ban 이 있어도 뚫릴 수 있다)
#   - 카페 비밀번호도 다른 곳과 겹치지 않게
#   - push 할 일이 없으면 배포 키를 만들지 않는다
#   - 서비스 계정에는 이 자동화에 필요한 시트만 공유한다
#   - 이 서버에서 커밋하기 전에 git 사용자 정보를 확인한다 (비어 있으면 서버 기본 이메일이 기록되어
#     그 이메일을 등록한 무관한 GitHub 계정이 작성자로 표시된다)
#   - 옛 서버를 정리할 때 옛 서버의 .env / credentials.json / 배포 키도 함께 없앤다
#
# ---------------------------------------------------------------------
# 4. 침입이 의심될 때
# ---------------------------------------------------------------------
#   확인:   last -n 20                       최근 로그인 기록 (모르는 IP 가 있는지)
#           fail2ban-client status sshd      차단 현황 (nft list ruleset 로도 확인, iptables -S 에는 안 나옴)
#           ss -ltnp                         열려 있는 포트와 프로세스
#           journalctl -u webhook -n 100 --no-pager
#   교체:   root 비밀번호(passwd) → WEBHOOK_SECRET (Apps Script 의 값도 함께)
#           → 카페 비밀번호 → 서비스 계정 키 (옛 키 삭제, GitHub Actions 의 GOOGLE_CREDENTIALS 시크릿도 함께)
#           → 배포 키 (GitHub Deploy keys 에서 삭제 후 새로 등록)
#   그래도 못 믿겠으면 서버를 새로 만든다 (README 의 가이드 그대로 다시 진행)
#
# ---------------------------------------------------------------------
# 5. 그 밖의 알려진 위험 (지금은 감수하고 있는 것)
# ---------------------------------------------------------------------
#   - 웹훅이 root 로 실행된다 (webhook.py 97행의 venv 경로가 /root/myproject/... 로 고정되어 있어 전용 계정으로
#     옮기려면 sys.executable 등으로 바꿔야 함)
#   - 주소가 http:// 라서 토큰이 평문으로 오간다. 필요하면 도메인 + nginx + certbot 으로 HTTPS 를 적용하고
#     5000 포트는 닫고 443 만 연다 (ufw delete allow 5000/tcp, ufw allow 443/tcp)
#   - WEBHOOK_SECRET 이 없으면 기본값 changeme 로 동작한다. 직접 만든 서버라면 값이 비었을 때
#     시작되지 않게 해야 한다 (None != None 이 거짓이라 secret 을 빼고 보내도 통과함)
#   - 관리자 계정을 만들면 sudo 가 비밀번호 없이(NOPASSWD:ALL) 허용된다 (01_bootstrap.sh). 키가 유출되면 곧바로 root 권한
#
# ---------------------------------------------------------------------
# 6. SSH 키 로그인으로 전환하기 (이 스크립트가 하는 일)
# ---------------------------------------------------------------------
#   SSH 키는 비밀번호 대신 쓰는 열쇠 한 쌍이다. 공개 키(.pub)는 서버에 등록하는 자물쇠이고 남에게 보여도 안전하며,
#   개인 키(.pub 가 없는 파일)는 내 PC 에만 두고 절대 남에게 주지 않는다 (채팅, 메일, GitHub 에 올리지 않기).
#   서버는 개인 키를 가진 사람만 들여보내므로, 비밀번호를 무작위로 대입하는 공격이 통하지 않는다.
#
#   1) 내 PC 에서 키를 만든다 (엔터만 눌러도 됨):
#        ssh-keygen -t ed25519
#      공개 키 확인:  cat ~/.ssh/id_ed25519.pub   (윈도우 PowerShell: type $env:USERPROFILE\.ssh\id_ed25519.pub)
#   2) 서버에서 01_bootstrap.sh 를 관리자 계정과 함께 실행해 공개 키를 등록한다:
#        ADMIN_USER=내이름 ADMIN_SSH_PUBKEY="ssh-ed25519 AAAA... me@pc" bash 01_bootstrap.sh
#      (이미 비밀번호 방식으로 만든 서버에 다시 실행하는 경우, 스왑/계정/저장소/venv 등 이미 있는 것은 건너뛰도록
#       만들었지만 실제로 재실행해 본 적은 없다. 먼저 DRY_RUN=1 로 확인한다)
#   3) [반드시 먼저] 새 터미널에서 `ssh <ADMIN_USER>@<서버IP>` 가 키로 접속되고 `sudo -n true` 가 되는지 직접 확인하고,
#      지금 쓰는 이 터미널은 닫지 않고 그대로 둔다
#   4) 이 스크립트를 실행한다 (비밀번호 로그인과 root 로그인이 꺼진다):
#        ADMIN_USER=myname CONFIRM_KEY_LOGIN_TESTED=yes bash 02_harden_ssh.sh
#   5) 새 터미널을 하나 더 열어서 다시 접속되는지 확인한다.
#      이후 작업은 관리자 계정으로 접속해 sudo -i 로 root 가 되어 진행한다 (root 로그인은 막힘)
#
#   개인 키를 잃어버리면 그 PC 로는 접속할 수 없다 (업체 웹 콘솔로는 들어갈 수 있음).
#   다른 PC 에서 접속하려면 그 PC 에서 키를 새로 만들어 서버에 추가로 등록한다.
#
# 잠겼을 때: 서버 업체(예: Vultr) 웹 콘솔로 접속해서
#   rm /etc/ssh/sshd_config.d/00-hardening.conf && systemctl reload ssh
#
# 이 스크립트가 파일 이름을 00- 으로 하는 이유는 아래 content 위의 주석 참고.
# 다른 곳에서 만든 fail2ban 이 공격을 못 잡을 때: OpenSSH 9.8+ 는 로그인 실패를 sshd-session 프로세스가 남기므로
#   journalmatch = _SYSTEMD_UNIT=ssh.service 로 넓혀야 한다 (01_bootstrap.sh 에 반영되어 있음).
# =====================================================================
set -euo pipefail

ADMIN_USER="${ADMIN_USER:-}"
CONFIRM="${CONFIRM_KEY_LOGIN_TESTED:-no}"
DRY_RUN="${DRY_RUN:-0}"
CONF=/etc/ssh/sshd_config.d/00-hardening.conf

die() { printf '\033[1;31m[오류] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$DRY_RUN" = 1 ] || [ "$(id -u)" = 0 ] || die "root 로 실행하세요 (sudo -i 후 다시)"
[ -n "$ADMIN_USER" ] || die "ADMIN_USER 가 필요합니다"
[ "$CONFIRM" = yes ] || die \
"새 터미널에서 키 로그인이 되는 것을 확인하셨다면 CONFIRM_KEY_LOGIN_TESTED=yes 를 붙여 다시 실행하세요.
    (확인하지 않고 끄면 서버에 못 들어올 수 있어 막아 두었습니다)"

home_dir="$(getent passwd "$ADMIN_USER" 2>/dev/null | cut -d: -f6 || true)"
home_dir="${home_dir:-/home/$ADMIN_USER}"
keyfile="$home_dir/.ssh/authorized_keys"

if [ "$DRY_RUN" != 1 ]; then
  id "$ADMIN_USER" >/dev/null 2>&1 || die "계정이 없습니다: $ADMIN_USER"
  [ -s "$keyfile" ] || die "$keyfile 이 비어 있습니다. 키가 등록되지 않았으면 끄면 안 됩니다"
  ssh-keygen -l -f "$keyfile" >/dev/null 2>&1 || die "$keyfile 에 올바른 공개키가 없습니다"
  id -nG "$ADMIN_USER" | tr ' ' '\n' | grep -qx sudo || die "$ADMIN_USER 는 sudo 권한이 없습니다 (root 로그인을 끄면 관리할 수 없게 됩니다)"
fi

# 파일 이름이 00- 인 이유: sshd 는 설정 파일을 이름 순으로 읽고 '먼저 나온 값'을 씁니다.
# cloud-init 이 만드는 50-cloud-init.conf 에 PasswordAuthentication yes 가 있어서,
# 99- 처럼 뒤에 두면 이 설정이 무시됩니다.
content='PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 3
'

if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] $CONF 를 아래 내용으로 작성하고 ssh 를 reload 합니다"
  printf '%s' "$content" | sed 's/^/    | /'
  exit 0
fi

backup=""
[ -f "$CONF" ] && { backup="$(mktemp)"; cp "$CONF" "$backup"; }
printf '%s' "$content" > "$CONF"
chmod 644 "$CONF"

rollback() {
  if [ -n "$backup" ]; then cp "$backup" "$CONF"; else rm -f "$CONF"; fi
  die "$1 (변경을 되돌렸습니다)"
}

sshd -t || rollback "sshd 설정 문법 검사 실패"

effective="$(sshd -T)"
echo "$effective" | grep -qi '^passwordauthentication no'  || rollback "비밀번호 로그인이 여전히 켜져 있습니다 (다른 설정 파일이 우선함)"
echo "$effective" | grep -qi '^permitrootlogin no'         || rollback "root 로그인이 여전히 켜져 있습니다 (다른 설정 파일이 우선함)"

systemctl reload ssh 2>/dev/null || systemctl reload sshd

echo
echo "적용 완료: 비밀번호 로그인 OFF, root 로그인 OFF"
echo "지금 이 터미널은 닫지 말고, 새 터미널에서 다시 한 번 접속되는지 확인하세요:"
echo "    ssh $ADMIN_USER@<서버IP>"
echo "그리고 (옵션) 비밀번호 로그인이 막혔는지 확인:"
echo "    ssh -o PubkeyAuthentication=no $ADMIN_USER@<서버IP>   # Permission denied 가 나와야 정상"
