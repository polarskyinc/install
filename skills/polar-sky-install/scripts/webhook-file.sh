#!/usr/bin/env bash
# Moves a webhook receiver's URL and signing secret between the clipboard and ~/polar-sky-install/webhook-endpoint.txt (URL on line 1, secret on line 2) without ever printing them: it prints only fixed words and, for a URL, its host.
set +x
exec 2>/dev/null
set -u
umask 077
export LC_ALL=C

folder="${HOME}/polar-sky-install"
file="${folder}/webhook-endpoint.txt"
placeholder='Replace this line with the receiver URL'
url_pattern='^https?://([A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?)([/?#][^[:space:][:cntrl:]]*)?$'
maximum_url_bytes=2048
maximum_secret_bytes=1024
kind=""
temporary=""
first=""
second=""
value=""

say() { printf '%s\n' "$1"; }

finish() {
  say "$1"
  exit "${2:-0}"
}

usage() { finish "usage: webhook-file.sh create|copy-secret|copy-text|paste-url|paste-secret|open" 2; }

have() { command -v "$1" >/dev/null 2>&1; }

remove_temporary() {
  if [ -n "${temporary}" ]; then
    rm -f "${temporary}"
  fi
}
trap remove_temporary EXIT

make_temporary() {
  temporary="$(mktemp "${folder}/.webhook-file.XXXXXX")" && [ -n "${temporary}" ]
}

over_ssh() { [ -n "${SSH_CONNECTION:-}" ] || [ -n "${SSH_TTY:-}" ]; }

find_clipboard() {
  if over_ssh; then
    return 1
  elif have pbcopy && have pbpaste; then
    kind=macos
  elif have clip.exe && have powershell.exe; then
    kind=windows
  elif [ -n "${WAYLAND_DISPLAY:-}" ] && have wl-copy && have wl-paste; then
    kind=wayland
  elif [ -n "${DISPLAY:-}" ] && have xclip; then
    kind=xclip
  elif [ -n "${DISPLAY:-}" ] && have xsel; then
    kind=xsel
  else
    return 1
  fi
}

write_clipboard() {
  case "${kind}" in
    macos) pbcopy ;;
    windows) clip.exe ;;
    wayland) wl-copy ;;
    xclip) xclip -selection clipboard -in ;;
    xsel) xsel --clipboard --input ;;
    *) return 1 ;;
  esac >/dev/null 2>&1
}

read_clipboard() {
  case "${kind}" in
    macos) pbpaste ;;
    windows) powershell.exe -NoProfile -Command Get-Clipboard ;;
    wayland) wl-paste --no-newline ;;
    xclip) xclip -selection clipboard -out ;;
    xsel) xsel --clipboard --output ;;
    *) return 1 ;;
  esac
}

clear_clipboard() {
  local left
  case "${kind}" in
    wayland) wl-copy --clear >/dev/null 2>&1 ;;
    xsel) xsel --clipboard --clear >/dev/null 2>&1 ;;
    *) printf '' | write_clipboard ;;
  esac || return 1
  left="$(read_clipboard)" || return 0
  left="${left//$'\r'/}"
  [ -z "${left//[[:space:]]/}" ]
}

finish_after_paste() {
  if clear_clipboard; then
    finish "$1"
  fi
  say "$1"
  finish "clipboard not cleared"
}

copy_and_check() {
  local copied
  printf '%s' "$1" | write_clipboard || return 1
  copied="$(read_clipboard)" || return 2
  copied="${copied//$'\r'/}"
  [ "${copied}" = "$1" ] || return 2
}

require_file() {
  if [ ! -f "${file}" ]; then
    finish "no file" 1
  fi
}

require_clipboard() {
  if ! find_clipboard; then
    finish "no clipboard" 3
  fi
}

read_lines() {
  first=""
  second=""
  # Bash 3.2 reports success for a failed redirect under `if !`, so redirects are tested in the positive form or with ||.
  if {
    IFS= read -r first
    IFS= read -r second
    true
  } <"${file}"; then
    first="${first%$'\r'}"
    second="${second%$'\r'}"
    return 0
  fi
  finish "file not readable" 1
}

write_lines() {
  make_temporary || finish "not saved" 1
  printf '%s\n%s\n' "$1" "$2" >"${temporary}" || finish "not saved" 1
  mv -f "${temporary}" "${file}" || finish "not saved" 1
  temporary=""
}

read_pasted_value() {
  value="$(read_clipboard)" || finish "no clipboard" 3
  value="${value//$'\r'/}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
}

create() {
  have openssl || finish "openssl missing" 1
  mkdir -p "${folder}" || finish "not created" 1
  if [ -e "${file}" ]; then
    finish "file exists" 1
  fi
  make_temporary || finish "not created" 1
  { printf '%s\n' "${placeholder}"; openssl rand -hex 32; } >"${temporary}" || finish "openssl missing" 1
  if ! ln "${temporary}" "${file}"; then
    if [ -e "${file}" ]; then
      finish "file exists" 1
    fi
    finish "not created" 1
  fi
  finish created
}

copy_secret() {
  require_file
  read_lines
  if [ -z "${second}" ]; then
    finish "no secret" 1
  fi
  require_clipboard
  copy_and_check "${second}"
  case "$?" in
    0) finish copied ;;
    1) finish "no clipboard" 3 ;;
  esac
  if clear_clipboard; then
    finish "no clipboard" 3
  fi
  say "no clipboard"
  finish "clipboard not cleared" 3
}

copy_text() {
  local text
  require_clipboard
  if [ -t 0 ]; then
    finish "nothing to copy" 1
  fi
  text="$(cat)"
  if [ -z "${text}" ]; then
    finish "nothing to copy" 1
  fi
  copy_and_check "${text}" || finish "no clipboard" 3
  finish copied
}

paste_url() {
  local host
  require_file
  read_lines
  require_clipboard
  read_pasted_value
  if [ "${#value}" -gt "${maximum_url_bytes}" ] || ! [[ ${value} =~ ${url_pattern} ]]; then
    finish "not a URL" 1
  fi
  host="${BASH_REMATCH[1]}"
  write_lines "${value}" "${second}"
  finish_after_paste "host: ${host}"
}

paste_secret() {
  require_file
  read_lines
  require_clipboard
  read_pasted_value
  case "${value}" in
    http://* | https://*) finish "looks like a URL" 1 ;;
  esac
  if [ -z "${value}" ] || [ "${#value}" -gt "${maximum_secret_bytes}" ]; then
    finish "not a secret" 1
  fi
  case "${value}" in
    *[[:cntrl:]]*) finish "not a secret" 1 ;;
  esac
  write_lines "${first}" "${value}"
  finish_after_paste saved
}

open_file() {
  local windows_path
  require_file
  if over_ssh; then
    finish "not opened" 1
  fi
  if [ "$(uname -s)" = Darwin ] && have open; then
    open -e "${file}" >/dev/null 2>&1 && finish opened
  elif have cmd.exe && have wslpath; then
    windows_path="$(wslpath -w "${file}")" &&
      cmd.exe /c start "" notepad.exe "${windows_path}" >/dev/null 2>&1 && finish opened
  fi
  finish "not opened" 1
}

[ "$#" -eq 1 ] || usage
case "$1" in
  create) create ;;
  copy-secret) copy_secret ;;
  copy-text) copy_text ;;
  paste-url) paste_url ;;
  paste-secret) paste_secret ;;
  open) open_file ;;
  *) usage ;;
esac
