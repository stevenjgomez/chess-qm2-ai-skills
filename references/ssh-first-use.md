# CHESS / CLASSE SSH First-Time Setup & Non-Interactive Access Guide

This guide establishes reliable, unattended SSH access to the CHESS/CLASSE login gateway (`lnx201.classe.cornell.edu`) for both human users and AI assistants (such as Antigravity, Gemini CLI, Claude Code, and OpenAI Codex).

---

## 1. Why Unattended SSH Authentication is Mandatory

When an AI assistant or automated orchestrator manages CHESS workflows (e.g. data reduction, status monitoring via `qstat`, or reciprocal slicing), it executes remote commands non-interactively via subprocesses.

> [!WARNING]
> **The "Interactive Terminal Trap": Why Logging In Separately Does Not Work**
>
> When an unattended SSH command stalls on a password or 2FA prompt, assistants frequently ask the user: *"Please log in to SSH in your terminal."*
>
> However, SSH sessions authenticated via one-shot passwords or keyboard-interactive Duo 2FA in a separate terminal **do NOT authenticate subsequent background or agent commands**. Each new `ssh` invocation launches a separate process requiring fresh credentials. Without key-based authentication or connection multiplexing, the assistant becomes trapped in an infinite loop asking the user to log in again and again.

### Core Security & Etiquette Principles
1. **Private Keys Stay Local**: The private key (`id_ed25519_classe`) must never leave the user's local machine and must never be transmitted over chat, logs, or scripts.
2. **Never Paste Credentials in Chat**: Passwords and passphrases must be entered directly in interactive terminal prompts, never provided to the AI assistant in chat.
3. **Preserve Existing Configurations**: Never overwrite existing keys or remove entries from remote `~/.ssh/authorized_keys`. Always append non-destructively.
4. **Login Node Etiquette**: SSH access connects only to `lnx201.classe.cornell.edu` for file inspection, job monitoring (`qstat`), and job submission (`qsub`). **No data processing or compute may be executed directly on `lnx201`**.

---

## 2. Pre-Flight Connection Check (Zero-Impact Verification)

Before preparing an analysis workflow or prompting for credentials, the assistant must run a fast, non-blocking pre-flight probe using `BatchMode=yes`:

### macOS / Linux / Bash
```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 <username>@lnx201.classe.cornell.edu 'echo CHESS_SSH_OK'
```

### Windows (PowerShell)
```powershell
$classeUser = 'YOUR_CLASSE_USERNAME'
$classeHost = 'lnx201.classe.cornell.edu'

ssh -o BatchMode=yes -o ConnectTimeout=15 `
    "${classeUser}@${classeHost}" 'echo CHESS_SSH_OK'
```

- **If exit code is 0 and output contains `CHESS_SSH_OK`**:
  Authentication is already working! Reuse existing access immediately and proceed with the scientific task. **Do not create new keys or alter configuration.**
- **If exit code is non-zero (Authentication failed / Permission denied)**:
  Unattended access is not configured. Guide the user through the platform-appropriate setup below.

---

## 3. Platform-Specific Setup Guides

### 3.1 Windows Setup (PowerShell 5.1 & PowerShell 7)

Windows environments require special care due to native-command quoting differences and carriage-return (`\r\n`) line ending issues. Follow this tested procedure:

#### Step 1: Establish Account Details & Generate Local Ed25519 Key
Ask the user for their CLASSE username. Define the dedicated key path:

```powershell
$classeUser = 'YOUR_CLASSE_USERNAME'
$classeHost = 'lnx201.classe.cornell.edu'
$classeKey  = Join-Path $env:USERPROFILE '.ssh\id_ed25519_classe'

if ((Test-Path -LiteralPath $classeKey) -or (Test-Path -LiteralPath ($classeKey + '.pub'))) {
    Write-Warning "A CLASSE key file already exists at $classeKey. Inspect and reuse it, or choose another filename."
} else {
    ssh-keygen -t ed25519 -a 100 -f $classeKey -C "${classeUser}@CLASSE"
}
```
*Note: Let `ssh-keygen` prompt interactively in the terminal. If the user prefers a passphrase-protected key, they enter the passphrase. If the user explicitly opts for no passphrase, they press Enter twice.*

#### Step 2: Configure SSH Agent (If Passphrase Protected)
If a passphrase was used, load the key into the Windows OpenSSH Authentication Agent:

```powershell
# Check if ssh-agent service is running
Get-Service ssh-agent | Select-Object -Property Status, StartType

# If stopped or disabled, start it (requires administrative PowerShell):
# Set-Service -Name ssh-agent -StartupType Automatic
# Start-Service ssh-agent

# Load key into agent
ssh-add $classeKey
```

#### Step 3: Safely Install Public Key on CLASSE Gateway
Windows lacks `ssh-copy-id`. Piping raw strings via PowerShell native commands often corrupts quotes or appends Windows CRLF line endings to `authorized_keys`.

Use this robust Base64-encoded installation script, which runs interactively (prompting once for password/Duo), normalizes line endings to Unix `\n`, and appends the key only if not already present:

```powershell
$publicKey = (Get-Content -LiteralPath ($classeKey + '.pub') -Raw).Trim()
if (-not $publicKey.StartsWith('ssh-ed25519 ')) {
    throw 'Expected an Ed25519 public key in .pub file.'
}

$publicKeyBase64 = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes($publicKey + "`n")
)

$installScript = @'
set -eu
public_key=$(printf '%s' '__PUBLIC_KEY_BASE64__' | base64 -d)
umask 077
mkdir -p "$HOME/.ssh"
authorized="$HOME/.ssh/authorized_keys"
if ! grep -qxF -- "$public_key" "$authorized" 2>/dev/null; then
  printf '\n%s\n' "$public_key" >> "$authorized"
fi
printf 'CHESS_PUBLIC_KEY_INSTALLED\n'
'@

$installScript = $installScript.Replace('__PUBLIC_KEY_BASE64__', $publicKeyBase64)
$installScript = $installScript.Replace("`r", '')
$scriptBase64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($installScript))
$installCommand = 'printf %s ' + $scriptBase64 + ' | base64 -d | bash'

# Execute in visible terminal so user authenticates once with password/2FA:
ssh -o BatchMode=no -o NumberOfPasswordPrompts=1 -o ConnectTimeout=20 `
    "${classeUser}@${classeHost}" $installCommand

if ($LASTEXITCODE -ne 0) {
    throw 'Public-key installation failed. Check the reported error before proceeding.'
}
```

#### Step 4: Verify Fresh Automatic Connection
Verify unattended access using the newly installed key:

```powershell
$probe = ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 `
    -i $classeKey "${classeUser}@${classeHost}" 'echo CHESS_SSH_OK'

if ($LASTEXITCODE -ne 0 -or @($probe) -notcontains 'CHESS_SSH_OK') {
    throw 'Automatic SSH authentication is not verified. Do not start unattended work yet.'
}

Write-Host 'SSH access successfully verified! Resuming CHESS task.' -ForegroundColor Green
```

#### Step 5: (Optional) Add Host Alias to `~/.ssh/config`
To allow simple `ssh lnx201` invocations, add this entry to `~/.ssh/config` (creating the file if needed):

```sshconfig
Host lnx201.classe.cornell.edu lnx201 classe
    HostName lnx201.classe.cornell.edu
    User YOUR_CLASSE_USERNAME
    IdentityFile ~/.ssh/id_ed25519_classe
    IdentitiesOnly yes
```

---

### 3.2 macOS Setup (Terminal / zsh)

#### Step 1: Generate Local Ed25519 Key
```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519_classe -C "<username>@classe"
```

#### Step 2: Store Passphrase in Apple Keychain
If passphrase-protected, persist the passphrase across logins using macOS Keychain:

```bash
ssh-add --apple-use-keychain ~/.ssh/id_ed25519_classe
```

#### Step 3: Install Public Key onto CLASSE Gateway
```bash
ssh-copy-id -i ~/.ssh/id_ed25519_classe.pub <username>@lnx201.classe.cornell.edu
```
*(Authenticate once interactively with CLASSE password and Duo 2FA).*

#### Step 4: Configure `~/.ssh/config`
Append or edit `~/.ssh/config`:

```sshconfig
Host lnx201.classe.cornell.edu lnx201 classe
    HostName lnx201.classe.cornell.edu
    User <username>
    IdentityFile ~/.ssh/id_ed25519_classe
    IdentitiesOnly yes
    AddKeysToAgent yes
    UseKeychain yes
```

#### Step 5: Verify Fresh Connection
```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 lnx201 'echo CHESS_SSH_OK'
```

---

### 3.3 Linux Setup (bash / zsh)

#### Step 1: Generate Local Ed25519 Key
```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519_classe -C "<username>@classe"
```

#### Step 2: Load Key into SSH Agent
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_classe
```

#### Step 3: Install Public Key onto CLASSE Gateway
```bash
ssh-copy-id -i ~/.ssh/id_ed25519_classe.pub <username>@lnx201.classe.cornell.edu
```

#### Step 4: Configure `~/.ssh/config`
```sshconfig
Host lnx201.classe.cornell.edu lnx201 classe
    HostName lnx201.classe.cornell.edu
    User <username>
    IdentityFile ~/.ssh/id_ed25519_classe
    IdentitiesOnly yes
    AddKeysToAgent yes
```

#### Step 5: Verify Fresh Connection
```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 lnx201 'echo CHESS_SSH_OK'
```

---

## 4. Alternative Authentication Pathways

If institutional policy prohibits standalone public-key authentication or enforces interactive 2FA on every handshake, use one of these alternative pathways:

### Pathway B: SSH Connection Multiplexing (`ControlMaster`)
You authenticate once in an interactive terminal with password and Duo 2FA. All subsequent background or assistant commands reuse the persistent master socket:

```sshconfig
Host lnx201.classe.cornell.edu lnx201 classe
    HostName lnx201.classe.cornell.edu
    User <username>
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h:%p
    ControlPersist 4h
```
*(Initialize the socket directory with `mkdir -p ~/.ssh/sockets` and connect once via `ssh lnx201` in your terminal).*

### Pathway C: Kerberos / GSSAPI Ticket Delegation
For Cornell-managed workstations with local Kerberos integration:
```bash
kinit <username>@CLASSE.CORNELL.EDU
```
In `~/.ssh/config`:
```sshconfig
Host lnx201.classe.cornell.edu lnx201 classe
    HostName lnx201.classe.cornell.edu
    User <username>
    GSSAPIAuthentication yes
    GSSAPIDelegateCredentials yes
```

---

## 5. Troubleshooting Decisions Matrix

| Symptom / Observation | Root Cause | Actionable Correction |
| :--- | :--- | :--- |
| **Password login worked earlier, but new command fails** | Completed one-shot SSH commands do not leave a reusable session for new child processes. | Guide user through public key or multiplexing setup. Explain that unattended agent commands require non-interactive keys or `ControlMaster`. |
| **Key installation printed success, but `BatchMode=yes` still fails** | Mismatched key identity, incorrect remote permissions, or CRLF corruption in `~/.ssh/authorized_keys`. | On `lnx201`, verify permissions: `chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys`. Check key fingerprint with `ssh-keygen -lf ~/.ssh/id_ed25519_classe.pub`. Verify remote line contains only Unix `\n`. |
| **Windows remote commands fail with `\r: command not found`** | Windows CRLF line endings were piped into remote bash. | Normalize line endings to LF (`\n`) using the Base64 script in Section 3.1. Avoid raw string pipelines in PowerShell. |
| **Protected key works in user terminal but fails in assistant agent** | Agent process cannot access the running `ssh-agent` or Keychain context. | Check agent availability (`ssh-add -l`). On Windows, ensure `ssh-agent` service is running. If necessary, user may opt for a dedicated passphrase-free key restricted to `lnx201`. |
| **Server prompts for Duo 2FA on every key connection** | Strict institutional Duo SSH policy without public-key bypass. | Configure Connection Multiplexing (Pathway B). User logs in once per 4-hour window, and all assistant jobs tunnel through the master connection. |
| **Valid key already exists on disk** | User already has a working SSH key pair. | Reuse existing key. Do not overwrite or create redundant keys. Test with `BatchMode=yes`. |

---

## 6. Acceptance Criteria for AI Assistants

When assisting a user with a CHESS remote workflow:
1. **Pre-flight Probe First**: Always test unattended access with `ssh -o BatchMode=yes -o ConnectTimeout=15 ... 'echo CHESS_SSH_OK'` before preparing analysis jobs.
2. **Never Loop on Password Requests**: If unattended access fails, never ask the user to "log in in another terminal". Offer the one-time key setup.
3. **Respect Passphrase Preferences**: Always obtain the user's explicit choice regarding passphrase protection.
4. **Preserve Existing Configuration**: Never overwrite existing keys or alter unrelated entries in `authorized_keys`.
5. **Enforce Verification Gate**: Do not consider setup complete until a fresh `BatchMode=yes` connection succeeds and returns `CHESS_SSH_OK`.
6. **Seamless Transition**: Resume the requested scientific workflow immediately upon verification.
