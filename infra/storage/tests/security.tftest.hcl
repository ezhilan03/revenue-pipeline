mock_provider "azurerm" {}

variables {
  subscription_id = "00000000-0000-0000-0000-000000000000"
  location        = "eastus"
  storage_name    = "revenuetestarchive"
}

run "private_archive_defaults" {
  command = plan
  assert {
    condition     = azurerm_storage_account.archive.public_network_access_enabled == false
    error_message = "Archive must not expose a public network endpoint."
  }
  assert {
    condition     = azurerm_storage_account.archive.shared_access_key_enabled == false
    error_message = "Shared-key access must stay disabled."
  }
  assert {
    condition     = azurerm_storage_container.raw.container_access_type == "private"
    error_message = "Raw container cannot allow anonymous reads."
  }
  assert {
    condition     = azurerm_storage_account.archive.blob_properties[0].versioning_enabled
    error_message = "Archive versioning must remain enabled."
  }
}
