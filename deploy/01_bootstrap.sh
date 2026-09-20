#!/usr/bin/env bash
# =====================================================================
# 새 Ubuntu VM 초기 세팅 (root 로 실행)
#
# 현재 서버와 같은 구성을 만든다:
#   관리자 계정 + SSH 키 / ufw / fail2ban / 스왑 / Chrome / Python venv /
#   catfiestagitsheet235 저장소 / webhook.service / 로그 회전
#
# 사용 예:
#   ADMIN_USER=myname ADMIN_SSH_PUBKEY="ssh-ed25519 AAAA... me@pc" bash 01_bootstrap.sh
#
# 아무것도 바꾸지 않고 할 일만 미리 보려면:
#   DRY_RUN=1 ADMIN_USER=myname ADMIN_SSH_PUBKEY="ssh-ed25519 AAAA test" bash 01_bootstrap.sh
#
# 이 스크립트는 SSH 비밀번호 로그인/root 로그인을 끄지 않는다.
# (키 로그인이 되는지 확인하기 전에 끄면 서버에 못 들어오기 때문)
# 확인 후 02_harden_ssh.sh 를 따로 실행한다.
# =====================================================================
set -euo pipefail

# ---- 설정 (환경변수로 바꿀 수 있음) -----------------------------------
ADMIN_USER="${ADMIN_USER:-}"                 # 로그인용 일반 계정 (선택. 둘 다 비우면 root 비밀번호 로그인 그대로 사용)
ADMIN_SSH_PUBKEY="${ADMIN_SSH_PUBKEY:-}"     # 그 계정의 SSH 공개키 한 줄 (ADMIN_USER 와 함께 넣거나 둘 다 비우기)
REPO_URL="${REPO_URL:-https://github.com/codec23567/catfiestagitsheet235.git}"
REPO_DIR="${REPO_DIR:-/root/catfiestagitsheet235}"   # webhook.py 가 이 위치를 기준으로 동작
VENV_DIR="${VENV_DIR:-/root/myproject/venv}"         # webhook.py 97행에 이 경로가 고정되어 있음
WEBHOOK_PORT="${WEBHOOK_PORT:-5000}"
SWAP_GB="${SWAP_GB:-2}"                      # RAM 3GB 미만이고 스왑이 없을 때만 만든다
INSTALL_CHROME="${INSTALL_CHROME:-1}"
PUSH_DISABLED="${PUSH_DISABLED:-1}"          # 1 이면 이 서버에서 git push 를 막는다 (현재 서버와 동일)
DRY_RUN="${DRY_RUN:-0}"
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

# ---- 도우미 ------------------------------------------------------------
log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[주의] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[오류] %s\033[0m\n' "$*" >&2; exit 1; }

# DRY_RUN 일 때는 시스템을 바꾸는 명령이 실수로 직접 호출돼도 실행되지 않게 막는다
if [ "$DRY_RUN" = 1 ]; then
  for c in apt-get ufw systemctl adduser useradd usermod chmod chown mkdir install \
           git curl gpg visudo mkswap swapon fallocate ln mv cp; do
    eval "$c() { echo \"    [dry-run 차단] $c \$*\"; }"
  done
fi

run() {  # 명령을 보여주고, DRY_RUN 이 아니면 실행
  echo "+ $*"
  [ "$DRY_RUN" = 1 ] || "$@"
}

append_line() {  # append_line <파일> <줄>
  if [ "$DRY_RUN" = 1 ]; then echo "+ $1 에 한 줄 추가"; else printf '%s\n' "$2" >> "$1"; fi
}

write_file() {  # write_file <경로> <권한> ; 내용은 표준입력으로 받는다
  local path="$1" mode="$2" tmp
  tmp="$(mktemp)"; cat > "$tmp"
  if [ "$DRY_RUN" = 1 ]; then
    echo "+ 파일 작성: $path (권한 $mode)"; sed 's/^/    | /' "$tmp"; rm -f "$tmp"; return
  fi
  mkdir -p "$(dirname "$path")"
  install -m "$mode" "$tmp" "$path"
  rm -f "$tmp"
  echo "+ 파일 작성: $path"
}

# ---- 시작 전 검사 ------------------------------------------------------
[ "$DRY_RUN" = 1 ] || [ "$(id -u)" = 0 ] || die "root 로 실행하세요 (sudo -i 후 다시)"

# ADMIN_USER 와 ADMIN_SSH_PUBKEY 는 둘 다 넣거나 둘 다 비워야 한다.
# 둘 다 비우면 관리자 계정을 만들지 않고, root 비밀번호 로그인을 그대로 쓴다 (02_harden_ssh.sh 는 쓰지 않는다).
if [ -n "$ADMIN_USER" ] || [ -n "$ADMIN_SSH_PUBKEY" ]; then
  [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_SSH_PUBKEY" ] || die \
"ADMIN_USER 와 ADMIN_SSH_PUBKEY 는 함께 넣어야 합니다 (둘 다 비우면 비밀번호 방식으로 진행).
    예) ADMIN_USER=myname ADMIN_SSH_PUBKEY=\"\$(cat ~/.ssh/id_ed25519.pub)\" bash 01_bootstrap.sh"

  [[ "$ADMIN_USER" =~ ^[a-z][a-z0-9_-]{0,30}$ ]] || die "ADMIN_USER 형식이 올바르지 않습니다 (소문자로 시작, 영문 소문자/숫자/_/-)"
  [ "$ADMIN_USER" != root ] || die "ADMIN_USER 는 root 가 아닌 다른 이름이어야 합니다"
  [[ "$ADMIN_SSH_PUBKEY" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+|sk-ssh-ed25519@openssh.com)\  ]] \
    || die "ADMIN_SSH_PUBKEY 가 공개키 형식이 아닙니다 (ssh-ed25519 AAAA... 처럼 시작해야 함)"
else
  warn "ADMIN_USER/ADMIN_SSH_PUBKEY 가 없어서 비밀번호 방식으로 진행합니다. root 비밀번호를 길고 복잡하게 쓰세요 (.env 와 서비스 계정 키가 이 서버에 들어갑니다)"
fi
[ -f "$SCRIPT_DIR/requirements-server.txt" ] || die "$SCRIPT_DIR/requirements-server.txt 가 없습니다 (이 스크립트와 같은 폴더에 두세요)"

[ "$DRY_RUN" = 1 ] && warn "DRY_RUN: 아무것도 바꾸지 않고 할 일만 출력합니다"
. /etc/os-release 2>/dev/null || true
echo "OS: ${PRETTY_NAME:-알 수 없음} / 아키텍처: $(dpkg --print-architecture) / RAM: $(free -m | awk '/^Mem:/{print $2}')MB"

# ---- 1. 패키지 ---------------------------------------------------------
log "1/9 패키지 업데이트와 설치"
export DEBIAN_FRONTEND=noninteractive
run apt-get update -y
run apt-get upgrade -y
# python3-dev, build-essential: pip 가 C 확장 패키지를 직접 컴파일해야 할 때 필요하다 (미리 넣어 두는 보험)
run apt-get install -y ufw fail2ban git curl ca-certificates gnupg \
    python3 python3-venv python3-pip python3-dev build-essential \
    tzdata unattended-upgrades logrotate

# ---- 2. 스왑 -----------------------------------------------------------
log "2/9 스왑"
mem_mb="$(free -m | awk '/^Mem:/{print $2}')"
if [ "$(wc -l < /proc/swaps)" -gt 1 ]; then
  echo "이미 스왑이 있어서 건너뜁니다"
elif [ "$mem_mb" -lt 3000 ]; then
  run fallocate -l "${SWAP_GB}G" /swapfile
  run chmod 600 /swapfile
  run mkswap /swapfile
  run swapon /swapfile
  grep -qs '^/swapfile' /etc/fstab || append_line /etc/fstab "/swapfile none swap sw 0 0"
else
  echo "RAM ${mem_mb}MB 로 충분해서 스왑을 만들지 않습니다"
fi

# ---- 3. 관리자 계정 + SSH 키 -------------------------------------------
log "3/9 관리자 계정 (${ADMIN_USER:-만들지 않음})과 SSH 키"
if [ -z "$ADMIN_USER" ]; then
echo "ADMIN_USER 가 없어서 건너뜁니다 (root 비밀번호 로그인 유지)"
else
if id "$ADMIN_USER" >/dev/null 2>&1; then
  echo "계정이 이미 있습니다"
else
  run adduser --disabled-password --gecos "" "$ADMIN_USER"
fi
run usermod -aG sudo "$ADMIN_USER"

home_dir="$(getent passwd "$ADMIN_USER" 2>/dev/null | cut -d: -f6 || true)"
home_dir="${home_dir:-/home/$ADMIN_USER}"

run install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$home_dir/.ssh"
if ! grep -qsF "$ADMIN_SSH_PUBKEY" "$home_dir/.ssh/authorized_keys"; then
  append_line "$home_dir/.ssh/authorized_keys" "$ADMIN_SSH_PUBKEY"
fi
run chown "$ADMIN_USER:$ADMIN_USER" "$home_dir/.ssh/authorized_keys"
run chmod 600 "$home_dir/.ssh/authorized_keys"

# 비밀번호 없이(키 로그인만) 쓰는 계정이라 sudo 도 비밀번호 없이 허용한다
if [ "$DRY_RUN" = 1 ]; then
  echo "+ /etc/sudoers.d/90-$ADMIN_USER 작성 ($ADMIN_USER ALL=(ALL) NOPASSWD:ALL)"
else
  tmp_sudoers="$(mktemp)"
  printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$ADMIN_USER" > "$tmp_sudoers"
  visudo -cf "$tmp_sudoers" >/dev/null || die "sudoers 문법 오류"
  install -m 440 "$tmp_sudoers" "/etc/sudoers.d/90-$ADMIN_USER"
  rm -f "$tmp_sudoers"
fi
fi

# ---- 4. 방화벽 ---------------------------------------------------------
log "4/9 방화벽 (ufw)"
run ufw default deny incoming
run ufw default allow outgoing
run ufw allow 22/tcp            # 켜기 전에 SSH 를 먼저 허용한다 (잠금 방지)
run ufw allow "${WEBHOOK_PORT}/tcp"
run ufw --force enable

# ---- 5. fail2ban -------------------------------------------------------
log "5/9 fail2ban"
# journalmatch: OpenSSH 9.8+ 는 로그인 실패를 sshd-session 프로세스가 남기므로
# 프로세스 이름(_COMM)으로 좁히지 않고 ssh 서비스의 모든 로그를 본다
write_file /etc/fail2ban/jail.d/sshd-local.conf 644 <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
bantime.increment = true
bantime.factor = 2
bantime.maxtime = 1w
journalmatch = _SYSTEMD_UNIT=ssh.service
EOF
run systemctl enable fail2ban
run systemctl restart fail2ban

# ---- 6. Chrome ---------------------------------------------------------
log "6/9 Google Chrome (modify_* 스크립트의 selenium 이 사용)"
if [ "$INSTALL_CHROME" != 1 ]; then
  echo "INSTALL_CHROME=0 이라 건너뜁니다"
elif [ "$(dpkg --print-architecture)" != amd64 ]; then
  warn "amd64 가 아니라서 Chrome 을 건너뜁니다 (Google Chrome 은 amd64 만 제공). modify_* 스크립트는 동작하지 않습니다"
elif command -v google-chrome-stable >/dev/null 2>&1; then
  echo "이미 설치되어 있습니다: $(google-chrome-stable --version 2>/dev/null || true)"
else
  run curl -fsSL -o /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  run apt-get install -y /tmp/google-chrome.deb
  run rm -f /tmp/google-chrome.deb
  [ "$DRY_RUN" = 1 ] || [ -x /usr/bin/google-chrome ] || warn "/usr/bin/google-chrome 이 없습니다. 스크립트가 이 경로를 고정해서 씁니다"
fi

# ---- 7. 저장소 ---------------------------------------------------------
log "7/9 저장소"
if [ -d "$REPO_DIR/.git" ]; then
  echo "이미 있습니다: $REPO_DIR"
else
  run git clone "$REPO_URL" "$REPO_DIR"
fi
if [ "$PUSH_DISABLED" = 1 ]; then
  run git -C "$REPO_DIR" remote set-url --push origin DISABLED_pull_only
fi

# ---- 8. Python venv ----------------------------------------------------
log "8/9 Python venv ($VENV_DIR)"
echo "시스템 Python: $(python3 --version 2>&1)  (현재 서버: 3.14.4)"
run mkdir -p "$(dirname "$VENV_DIR")"
if [ ! -x "$VENV_DIR/bin/python3" ]; then
  run python3 -m venv "$VENV_DIR"
fi
run "$VENV_DIR/bin/pip" install --upgrade pip
run "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements-server.txt"

# ---- 9. webhook 서비스 + 로그 회전 -------------------------------------
log "9/9 webhook 서비스와 로그 회전"
write_file /etc/systemd/system/webhook.service 644 <<EOF
[Unit]
Description=Google Sheet Webhook Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python3 $REPO_DIR/webhook.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

write_file /etc/logrotate.d/catfiesta-webhook 644 <<EOF
$REPO_DIR/logs/*.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
EOF

run systemctl daemon-reload
run systemctl enable webhook

# webhook.py 는 시작할 때 .env 와 credentials.json 을 읽으므로 없으면 계속 죽는다
if [ -f "$REPO_DIR/.env" ] && [ -f "$REPO_DIR/credentials.json" ]; then
  run chmod 600 "$REPO_DIR/.env" "$REPO_DIR/credentials.json"
  run systemctl restart webhook
else
  warn ".env 와 credentials.json 이 아직 없어서 webhook 을 시작하지 않았습니다."
  echo "    옛 서버에서 복사한 뒤:  chmod 600 $REPO_DIR/.env $REPO_DIR/credentials.json && systemctl start webhook"
fi

# ---- 끝 ----------------------------------------------------------------
log "초기 세팅 완료"
if [ -z "$ADMIN_USER" ]; then
cat <<EOF
비밀번호 방식으로 진행했습니다 (관리자 계정 없음, SSH 는 그대로).
다음 순서로 진행하세요.

 1) .env / credentials.json 을 $REPO_DIR 에 넣고 webhook 시작 (README.md 3~4단계 참고)
 2) Apps Script 의 웹훅 주소를 새 서버로 변경하고 전환 테스트 (README.md 5·7단계 참고)

 * 02_harden_ssh.sh 는 실행하지 마세요 (관리자 계정이 없어서 실행할 수 없습니다).
 * root 비밀번호는 길고 복잡하게 유지하세요. fail2ban 이 반복 실패를 차단합니다.
EOF
exit 0
fi
cat <<EOF
다음 순서로 진행하세요.

 1) [중요] 지금 이 터미널은 닫지 말고, 새 터미널에서 키로 접속되는지 확인:
        ssh $ADMIN_USER@<새 서버 IP>
        sudo -n true && echo sudo OK
 2) 접속이 되면 SSH 비밀번호/root 로그인 차단:
        ADMIN_USER=$ADMIN_USER CONFIRM_KEY_LOGIN_TESTED=yes bash $SCRIPT_DIR/02_harden_ssh.sh
 3) .env / credentials.json 복사 후 webhook 시작 (README.md 참고)
 4) Apps Script 의 웹훅 주소를 새 서버로 변경하고 전환 테스트 (README.md 참고)
EOF
