# Security Policy

## Reporting a Vulnerability

**Please do NOT open public GitHub issues for security vulnerabilities.**

Instead, use GitHub's **private security vulnerability reporting**:

1. Go to the repository's **Security tab**
2. Click **"Report a vulnerability"** button
3. Fill out the vulnerability report form with:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)

This creates a **private security advisory** that only maintainers can see. This allows us to:
- Assess and fix the vulnerability before public disclosure
- Protect users by preventing details reaching bad actors before a patch exists
- Coordinate responsible disclosure timing with you

**GitHub's security reporting form ensures privacy during the fix process.**

## Response Timeline

We aim to:
- Acknowledge receipt within 48 hours
- Provide initial assessment within 1 week
- Release a fix within 2 weeks for critical vulnerabilities
- Coordinate disclosure timing with the reporter

## Vulnerability Disclosure

Once a fix is released, the vulnerability will be disclosed through:
- GitHub Security Advisory
- Release notes
- Security commit message

## Security Best Practices

When using ollama-catalog:

1. **Validate Input:** Never trust user-supplied model slugs or URLs without validation
2. **Use Latest Version:** Keep ollama-catalog updated for security patches
3. **Dependencies:** Monitor dependencies via Dependabot for vulnerability updates
4. **URLs:** Be cautious with dynamically constructed URLs to untrusted model sources

## Scope

This policy applies to:
- Code in the main repository
- Dependencies listed in `pyproject.toml`
- GitHub Actions workflows

## Security Features

- Input validation for model identifiers
- URL sanitization in model scrapers
- Regular dependency vulnerability scanning (via Dependabot)
- GitHub Actions security hardening
