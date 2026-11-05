# Releasing Belfry

Belfry is released together with belfry-ee, belfry-operator and the Helm chart, with one version for all of them (for example `1.0.0` or `1.0.0-rc.1`). The procedure for maintainers is in [RELEASING.md](https://github.com/belfry-project/.github/blob/main/RELEASING.md) in the belfry-project/.github repository.

In this repository, publishing a GitHub release runs the [Release](../.github/workflows/release.yml) workflow, which:

- builds `ghcr.io/belfry-project/belfry:<version>` for linux/amd64 and linux/arm64, and checks that the image reports the release version;
- tags it `:latest` as well for final releases (not for release candidates);
- attests build provenance and an SBOM, scans the image with Trivy, and attaches the SBOM and the scan to the release;
- attaches the `awx.awx` collection tarball and the awxkit sdist and wheel to the release (Belfry does not publish to Ansible Galaxy or PyPI).

Run the workflow manually with `dry_run` to test all of this without a release: it publishes only `:release-test` and keeps the files as workflow artifacts.
