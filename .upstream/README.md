# dailybuild upstream migration

Upstream: https://github.com/wkccd/dailybuild (main). The snapshot is recorded in dailybuild.sha; this is an independent repository, not a replacement GitHub fork parent.

- Existing 24.10/IPK workflows retain the original daily schedules and YYYY-MM-DD release tags. Existing DAE is retained.
- Optional 24.10 workflows are manual. 25.12/APK builds are manual, publish to openwrt25-YYYY-MM-DD prereleases, and do not replace the latest daily release. Xray uses a separate core- tag.
- Build selected plugin family dispatches only allowlisted build workflows. It never starts cleanup, Telegram or itself.
- On the test branch, build outputs are Actions artifacts, not releases. Cleanup and Telegram run only on daily.
- Upstream check generates a diff artifact for review; it does not execute remote code or automatically overwrite workflows. After reviewing and migrating changes, update dailybuild.sha to the reviewed commit.
- Validation checks workflow syntax and shell syntax, not the actual plugin builds or router compatibility. Run individual builds and test on matching router versions before merging. Newly added workflow_dispatch entries may require the workflow to exist on the default branch before GitHub exposes manual dispatch.
- Telegram keeps the existing weekly schedule and TG_BOT_TOKEN / TG_CHAT_ID secret names; sends only dated daily .run assets and splits long messages.
- Cleanup Old Releases only targets date-only daily release tags; Delete All Tags requires explicit DELETE-ALL-TAGS confirmation and is destructive.
- Rollback branch: backup/pre-dailybuild-migration.
