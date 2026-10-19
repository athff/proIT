# Roadmap

## Phase 0: Foundation (Current)

- [x] Project structure and directory layout
- [x] Engineering documentation (README, PRODUCT_REQUIREMENTS, ARCHITECTURE, DEVELOPMENT_RULES, ROADMAP)
- [x] .gitignore configured
- [x] Proposed technology stack documented (Django, DRF, PostgreSQL)
- [ ] Initial Django project scaffolding (startproject, app scaffolding)
- [ ] Base settings configuration
- [ ] PostgreSQL database schema foundation

## Phase 1: Core Asset Management

- [ ] `assets` app: Asset model, asset types, statuses
- [ ] `people` app: Employee, Department, Location models
- [ ] Basic API endpoints for asset and people CRUD
- [ ] Admin interface configuration
- [ ] Basic audit logging for asset changes
- [ ] Unit tests for core models and APIs

## Phase 2: Checkout/Check-in Workflow

- [ ] `checkouts` app: Checkout request, approval, check-in flow
- [ ] Check-out duration tracking and overdue detection
- [ ] Notification system for check-in reminders
- [ ] Checkout history and reporting
- [ ] API endpoints for checkout operations

## Phase 3: Accessories, Consumables, and Licenses

- [ ] `accessories` app: Accessory and Consumable models
- [ ] `licenses` app: Software License, Software Title models
- [ ] License expiration tracking and compliance reporting
- [ ] License assignment to assets or users

## Phase 4: Vendors, Maintenance, and Reporting

- [ ] `vendors` app: Vendor, MaintenanceContract, ServiceTicket models
- [ ] Repair history and warranty tracking
- [ ] `reporting` app: Custom queries, summary reports
- [ ] Notification system for maintenance due, expiring licenses
- [ ] Export capabilities (CSV, JSON)

## Phase 5: Authentication, Permissions, and Integrations

- [ ] `api` app: Authentication backends (Session, Token, JWT)
- [ ] Role-based access control (RBAC)
- [ ] API rate limiting and throttling
- [ ] Third-party integration webhooks
- [ ] LDAP/SSO integration framework

## Phase 6: Polish and Deployment

- [ ] Frontend templates (basic list/detail views)
- [ ] Search and filter across assets, employees, licenses
- [ ] Dashboard with key metrics
- [ ] Production configuration and deployment scripts
- [ ] CI/CD pipeline setup
- [ ] Documentation complete and published
- [ ] Initial public beta release

## Out of Scope (Future Considerations)

- Physical asset tracking via barcode/QR scanning integration
- Financial accounting integration (procurement, depreciation)
- Multi-tenant capability for reselling/service providers
- Mobile native applications
- IoT device tracking