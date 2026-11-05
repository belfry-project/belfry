[![CI](https://github.com/belfry-project/belfry/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/belfry-project/belfry/actions/workflows/ci.yml) [![Apache v2 License](https://img.shields.io/badge/license-Apache%202.0-brightgreen.svg)](./LICENSE.md)

<img src="./awx/static/belfry-icon.svg" width=120 alt="Belfry" />

# Belfry

Belfry provides a web-based user interface, REST API, and task engine built on top of [Ansible](https://github.com/ansible/ansible). It is a community continuation of [AWX](https://github.com/ansible/awx), whose releases are paused upstream, with maintained dependencies, security fixes and published images.

- Website and documentation: https://belfry-project.github.io/
- Install on Kubernetes with [belfry-operator](https://github.com/belfry-project/belfry-operator) or the [Helm chart](https://github.com/belfry-project/helm-charts).
- Container images: `ghcr.io/belfry-project/belfry`, execution environment `ghcr.io/belfry-project/belfry-ee`.
- The web UI is built from [belfry-ui](https://github.com/belfry-project/belfry-ui).

Belfry keeps AWX's internal names so existing installations, playbooks and scripts keep working: the Python package and CLI are still called `awx`, the API lives under `/api/v2/`, the Ansible collection is `awx.awx`, and the Kubernetes resources use the `awx.ansible.com` API group. The [comparison page](https://belfry-project.github.io/) lists what changed compared to AWX.

Credits
-------

Belfry is based on the work of the [AWX project](https://github.com/ansible/awx) and its contributors, including [AWX Operator](https://github.com/ansible/awx-operator), [AWX EE](https://github.com/ansible/awx-ee) and [Ansible UI](https://github.com/ansible/ansible-ui). The full upstream history is kept in this repository. Belfry is not affiliated with or endorsed by Red Hat, Inc.

AWX and Ansible are trademarks of Red Hat, Inc. Belfry does not use the AWX logos; see the [AWX trademark guidelines](https://github.com/ansible/awx-logos/blob/master/TRADEMARKS.md).

Contributing
------------

- Refer to the [Contributing guide](./CONTRIBUTING.md) to get started developing, testing, and building Belfry.
- All code submissions are made through pull requests against the `main` branch.
- All contributors must use `git commit --signoff` for any commit to be merged and agree that usage of `--signoff` constitutes agreement with the terms of [DCO 1.1](./DCO_1_1.md).
- Take care to make sure no merge commits are in the submission, and use `git rebase` vs. `git merge` for this reason.

Reporting Issues
----------------

If you're experiencing a problem that you feel is a bug in Belfry or have ideas for improving it, please open an [issue](https://github.com/belfry-project/belfry/issues). Before opening a new issue, take a look at the [Issues guide](./ISSUES.md). Report security problems as described in the [security policy](https://github.com/belfry-project/.github/blob/main/SECURITY.md).

License
-------

Belfry is licensed under the [Apache License 2.0](./LICENSE.md), like AWX.
