# Revised Standard Operating Procedure for Change Management

## Effective Date: [Insert Date]

### Purpose
This SOP ensures proper documentation, approval, and rollback processes for all changes to operational equipment.

### Key Improvements
- Mandatory ticket numbering
- Separated requester/approver roles
- Pre-execution backup verification
- Clear rollback criteria
- 24-hour post-approval requirement for urgent changes

## Procedure

### Regular Changes
1. **Ticket Creation**
   - Create a ticket with detailed change description, date, and requester
   - Document in change log (see Appendix A)
2. **Approval Process**
   - Requester submits ticket to team leader
   - Team leader approves via written confirmation
   - Approval must be separate from requester
3. **Execution**
   - Backup system state before changes
   - Execute changes following documented steps
   - Confirm backup recovery test success
4. **Rollback**
   - If failure occurs within 2 hours, immediately rollback
   - Document rollback原因 and corrective actions

### Urgent Changes
1. **Immediate Action**
   - Create emergency ticket with 'URGENT' flag
   - Execute changes following documented steps
2. **Post-Approval**
   - Team leader must approve within 24 hours
   - Document approval date and reason
3. **Documentation**
   - Add to change log with 'URGENT' designation

## Checklists
### Regular Change Checklist
- [ ] Ticket created
- [ ] Approval received
- [ ] Backup verified
- [ ] Execution completed
- [ ] Rollback tested (if failed)

### Urgent Change Checklist
- [ ] Emergency ticket created
- [ ] Immediate execution
- [ ] 24-hour approval obtained

## Responsibilities
- Requester: Submit ticket, document changes
- Approver: Verify requirements, sign off
- IT/Backup Team: Confirm backups, test recovery
- Supervisor: Monitor execution, approve urgent changes

## Appendix A: Change Log Format
| Ticket # | Date | Requester | Approver | Status | Notes |
|---------|------|----------|----------|--------|-------|
