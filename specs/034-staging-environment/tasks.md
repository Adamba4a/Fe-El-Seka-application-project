# Tasks: Isolated Staging Environment

- [x] T001 Document isolation boundaries and deployment approach.
- [x] T002 Publish branch-specific Docker tags and allow CI on `staging`.
- [x] T003 Add a VPS deployment bundle with an isolated network, staging image tags, and automatic TLS.
- [ ] T004 Provision the VPS, point the staging hostname to it, and configure isolated environment variables.
- [ ] T005 Create the separate Supabase staging project and apply migrations.
- [ ] T006 Configure the GitHub `staging` environment with the staging frontend build variables.
- [ ] T007 Create a dedicated verified staging passenger and run the staged read-only capacity test.
- [ ] T008 Record capacity findings and choose initial production scaling settings.
