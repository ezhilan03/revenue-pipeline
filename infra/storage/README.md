# Azure storage foundation — not applied

This bounded module defines a private archive account/container, versioning,
seven-day soft deletion and container-scoped ingestion identity access. It is not
the complete cloud deployment and is not connected to the current local Archive
implementation. No compute/database service or continuous cloud cost is activated.

Run `terraform init -backend=false`, `terraform validate`, and `terraform test`.
The tests use a mocked provider: they do not authenticate to Azure or prove live
deployment. Provider registration is disabled to avoid implicit registration writes.

Do not apply before billing/region/budget approval and cloud network design.
Public networking is disabled; private-endpoint/DNS access and an appropriately
connected deployment runner are required before data-plane use. Those network
resources are deliberately not guessed here. The storage identity can delete
blobs: Contributor is not a WORM guarantee. Locked immutability/retention policy
requires a separate reviewed decision because of irreversible retention effects.

The account has `prevent_destroy` for accidental Terraform deletion protection.
Before a real apply, configure a protected remote state backend and scoped OIDC
deployment identity. State can hold sensitive resource attributes even though this
module outputs no credentials. Do not commit `.tfstate` or credential-bearing vars.

Reference: [AzureRM storage account](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account).
