Concrete steps

1. After Claude finishes a feature, push the branch:
git push origin 006-frontend-design

2. Create a PR (but don't merge yet):
gh pr create --title "..." --body "..." --draft
The --draft flag signals "not ready to merge."

3. Give Antigravity the branch or PR URL. It can clone/pull just that branch:
git fetch origin 006-frontend-design
git checkout 006-frontend-design

4. Apply Gemini's fixes — either you apply them manually, or Claude applies them on the same branch and pushes again.

5. When review passes, mark PR ready and merge:
gh pr ready   # removes draft status
gh pr merge --squash