# Security Quick Reference Guide

## 🚀 Quick Start

### Before Committing
```bash
# Run local security check
./scripts/security-check.sh

# Or use pre-commit
pre-commit run --all-files
```

### Check Specific Issues
```bash
# Find hardcoded paths
grep -r "/home/chicha09" --exclude-dir=".git" .

# Find potential API keys
grep -r "API_KEY.*=.*['\"][a-zA-Z0-9_-]{20,}['\"]" --exclude-dir=".git" .
```

---

## 🛠️ Common Fixes

### Fix: Hardcoded Path
**Before:**
```bash
export PATH="/home/chicha09/.local/bin:$PATH"
```

**After:**
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Fix: Exposed API Key
**Before:**
```lua
api_key = "sk-1234567890abcdef"
```

**After:**
```lua
api_key = vim.env.MY_API_KEY or ""
```

---

## 🔍 Scanning Tools

### Gitleaks
```bash
# Install
brew install gitleaks

# Scan current state
gitleaks detect --source . --verbose

# Scan git history
gitleaks detect --source . --log-opts="--all" --verbose
```

### TruffleHog
```bash
# Install
brew install trufflesecurity/trufflehog/trufflehog

# Scan filesystem
trufflehog filesystem --directory .

# Scan git history
trufflehog git file://. --since-commit HEAD~10
```

### Trivy
```bash
# Install
brew install aquasecurity/trivy/trivy

# Scan for vulnerabilities
trivy fs .

# Scan specific config files
trivy config .
```

---

## ⚠️ What NOT to Commit

### Never Commit
- ❌ Credit card numbers
- ❌ Social security numbers
- ❌ Personal identification documents
- ❌ Medical records
- ❌ Financial statements

### Safe to Commit Unencrypted
- ✅ Configuration files (without secrets)
- ✅ Shell scripts (without credentials)
- ✅ Public SSH keys
- ✅ Documentation
- ✅ Themes and color schemes

---

## 🚨 Emergency Response

### If You Accidentally Commit a Secret

1. **DO NOT** just delete the file and commit again (it's still in history)
2. **Immediately rotate** the compromised credential
3. **Remove from git history**:
   ```bash
   # Using git-filter-repo (recommended)
   git filter-repo --path path/to/secret --invert-paths

   # Or using BFG Repo-Cleaner
   bfg --delete-files secret_file
   ```
4. **Force push** (if you own the repo):
   ```bash
   git push --force --all
   ```
5. **Notify team members** to re-clone the repository

### If You Find a Secret in History

```bash
# Find when it was added
git log --all --full-history -p -S "secret_pattern"

# Remove it
git filter-repo --path path/to/file --invert-paths

# Verify it's gone
git log --all --full-history -p -S "secret_pattern"
```

---

## 📊 Security Status Checks

### Pre-Push Checklist
```bash
# 1. Run security check
./scripts/security-check.sh

# 2. Check git status
git status

# 3. Review changes
git diff --cached

# 4. Verify no large files
git diff --cached --stat | grep -E '\|.*[0-9]{4,}'

# 5. Run pre-commit hooks
pre-commit run --all-files
```

### Post-Push Verification
1. Check GitHub Actions results
2. Review Security tab for alerts
3. Verify workflow passed
4. Check SARIF reports

---

## 🔗 Quick Links

- [Full Security Policy](../SECURITY.md)
- [Security Assessment Report](../SECURITY_ASSESSMENT.md)
- [Workflow Documentation](.github/workflows/README.md)

---

## 💡 Tips

### Tip 1: Use Environment Variables
Store secrets in your local environment variables and reference them:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Tip 2: Test Locally First
Always run `./scripts/security-check.sh` before pushing.

### Tip 3: Keep Tools Updated
```bash
brew upgrade gitleaks trufflehog trivy
```

---

**Last Updated**: November 15, 2025
