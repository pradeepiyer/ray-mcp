# Dependency Management Strategy

This document explains the automated dependency management strategy for the Ray MCP project.

## 🎯 Goals

- **Automated Updates**: Reduce manual dependency management overhead
- **Safety First**: Prevent breaking changes through smart version constraints
- **Continuous Integration**: Automated testing ensures updates don't break functionality
- **Transparency**: Clear visibility into dependency changes

## 📋 Version Strategy

### Version Constraints

We use **version ranges with upper bounds** to balance automation with safety:

```toml
# ✅ Good - Allows patch and minor updates, prevents breaking major updates
"pytest>=7.0.0,<8.0.0"

# ❌ Avoid - Too restrictive, requires manual updates
"pytest==7.4.3"

# ⚠️ Risky - Allows potentially breaking major version updates
"pytest>=7.0.0"
```

### Dependency Categories

#### 1. **Production Dependencies** (`[project.dependencies]`)
- **Conservative approach**: Allow minor and patch updates only
- **Examples**: `"ray[default]>=2.47.0,<3.0.0"`
- **Rationale**: These affect end users and should be stable

#### 2. **Development Dependencies** (`[tool.uv.dev-dependencies]`)
- **Moderate approach**: Allow minor and patch updates
- **Examples**: `"pytest>=7.0.0,<8.0.0"`
- **Rationale**: These only affect developers and can be updated more frequently

#### 3. **Optional Dependencies** (`[project.optional-dependencies]`)
- **Conservative approach**: Match production dependency strategy
- **Examples**: `"google-cloud-container>=2.17.0,<3.0.0"`
- **Rationale**: These affect specific use cases and should be stable

## 🔄 Update Methods

### 1. Automated Updates (Recommended)

#### GitHub Actions Workflow
- **Schedule**: Every Monday at 9 AM UTC
- **Process**: 
  1. Check for outdated packages
  2. Update within version constraints
  3. Run full test suite
  4. Create pull request if tests pass
  5. Auto-merge if all checks pass

#### Manual Trigger
You can also trigger the workflow manually:
```bash
# Go to GitHub Actions tab and trigger "Update Dependencies" workflow
```

### 2. Local Updates

#### Using the Update Script
```bash
# Interactive update with safety checks
make update-deps

# Or run directly
python scripts/update_dependencies.py
```

#### Manual UV Commands
```bash
# Check for outdated packages
uv pip list --outdated

# Update all dependencies
uv sync --dev --upgrade

# Update specific package
uv add "package>=x.y.z,<x+1.0.0"
```

## 🛡️ Safety Measures

### 1. Version Constraints
- **Upper bounds** prevent major version updates
- **Lower bounds** ensure minimum functionality
- **Semantic versioning** awareness

### 2. Automated Testing
- **Full test suite** runs on every update
- **Format and type checking** ensures code quality
- **Smoke tests** validate critical functionality

### 3. Review Process
- **Pull requests** for all automated updates
- **Clear change descriptions** in PR body
- **Manual review** option before merging

## 📊 Monitoring

### Check Dependency Status
```bash
# Check for outdated packages
make uv-check

# View dependency tree
uv tree

# Check for security vulnerabilities
uv pip audit
```

### Update Frequency
- **Automated**: Weekly (Mondays)
- **Manual**: As needed for security fixes
- **Major versions**: Manual review required

## 🔧 Configuration

### Version Constraint Updates
To update version constraints, edit `pyproject.toml`:

```toml
# Example: Allow newer major version
"pytest>=7.0.0,<9.0.0"  # Was: "pytest>=7.0.0,<8.0.0"
```

### Workflow Customization
Edit `.github/workflows/update-dependencies.yml`:

```yaml
# Change schedule
schedule:
  - cron: '0 9 * * 3'  # Wednesday instead of Monday

# Disable auto-merge
# Comment out the "Auto-merge" step
```

## 📚 Best Practices

### 1. Version Constraint Guidelines
- **Pin major versions** to prevent breaking changes
- **Allow minor/patch updates** for bug fixes and features
- **Use semantic versioning** knowledge when setting bounds

### 2. Testing Strategy
- **Always test** after dependency updates
- **Run full test suite** including integration tests
- **Check for deprecation warnings** in test output

### 3. Security Updates
- **Immediate updates** for security vulnerabilities
- **Override version constraints** if necessary for security
- **Document security-related updates** in commit messages

### 4. Major Version Updates
- **Manual review** required for major version updates
- **Create feature branch** for major version updates
- **Test thoroughly** with multiple scenarios
- **Update documentation** if APIs change

## 🚨 Troubleshooting

### Common Issues

#### 1. Update Fails Tests
```bash
# Check what changed
git diff uv.lock

# Revert problematic package
uv add "package>=old.version,<new.version"

# Run tests to verify
make test
```

#### 2. Dependency Conflicts
```bash
# View conflict details
uv pip check

# Force resolution
uv sync --dev --refresh

# Check dependency tree
uv tree
```

#### 3. Security Vulnerabilities
```bash
# Check for vulnerabilities
uv pip audit

# Update specific package
uv add "vulnerable-package>=fixed.version"
```

## 🎉 Benefits

### For Developers
- **Reduced maintenance** overhead
- **Automatic security updates**
- **Consistent development environment**

### For Users
- **Stable releases** with tested dependencies
- **Security patches** applied promptly
- **Predictable behavior** across versions

### For Project
- **Reduced technical debt** from outdated dependencies
- **Improved security posture**
- **Better compatibility** with ecosystem

## 🔄 Migration Guide

### From Manual Updates
1. **Review current dependencies** for appropriate version constraints
2. **Update pyproject.toml** with version ranges
3. **Enable GitHub Actions workflow**
4. **Run initial update** to validate setup

### From Other Tools
1. **Convert** existing dependency files to `pyproject.toml`
2. **Adjust version constraints** to match strategy
3. **Update CI/CD** to use UV commands
4. **Test thoroughly** after migration

---

> **Note**: This strategy balances automation with safety. Adjust constraints based on your project's specific needs and risk tolerance. 