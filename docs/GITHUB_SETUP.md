# GitHub repo settings — manual checklist for the owner (Task 0.5.3).
# These cannot be set from a clone; do them once in the repo's Settings tab.

## Branch protection (Settings → Branches → Add rule for `main`)
- [ ] Require a pull request before merging
- [ ] Require status checks to pass: `unit-tests`, `security-scan`
- [ ] Require conversation resolution before merging
- [ ] Do not allow bypassing the above settings

## Code security (Settings → Code security and analysis)
- [ ] Secret scanning: ON
- [ ] Push protection: ON  (blocks pushes containing keys — the 0.5 done-criteria)
- [ ] Dependabot alerts: ON (pip + github-actions — see .github/dependabot.yml)

## After enabling
Push a commit containing a fake key (e.g. `HUGGINGFACE_API_KEY=hf_1234567890abcdef`)
on a throwaway branch and confirm push protection blocks it. Then delete the branch.
