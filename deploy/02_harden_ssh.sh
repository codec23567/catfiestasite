#!/usr/bin/env bash
# =====================================================================
# SSH 강화: 비밀번호 로그인과 root 로그인을 끈다.
#
# [반드시 먼저]
#   1) 01_bootstrap.sh 를 실행했고
#   2) 새 터미널에서 `ssh <ADMIN_USER>@<서버IP>` 가 키로 접속되는 것을 직접 확인했고
#   3) 지금 쓰는 이 터미널은 닫지 않고 그대로 둔다
#
# 사용 예:
#   ADMIN_USER=myname CONFIRM_KEY_LOGIN_TESTED=yes bash 02_harden_ssh.sh
#
# 잠겼을 때: 서버 업체(예: Vultr) 웹 콘솔로 접속해서
#   rm /etc/ssh/sshd_config.d/00-hardening.conf && systemctl reload ssh
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
