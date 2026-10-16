## Description
<!-- Provide a brief description of the changes made and the motivation behind them. -->

## Changes Checklist
- [ ] Code follows the established PEP 8 / Ruff style guidelines (`make lint`)
- [ ] New and existing tests pass locally with coverage (`make test`)
- [ ] Database migrations are checked against models if schema changed (`alembic check`)
- [ ] Standard error response format maintained: `{"detail": "...", "code": "..."}`
- [ ] Timezone safety: all stored timestamps are UTC, display uses `Africa/Nairobi` (+03:00)

## Related Issue / Ticket
<!-- Closes #ISSUE_NUMBER or references task -->
