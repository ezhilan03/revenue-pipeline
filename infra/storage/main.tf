terraform {
  required_version = ">= 1.7, < 2.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  storage_use_azuread             = true
}

variable "subscription_id" {
  type = string
}

variable "location" {
  type        = string
  description = "Explicitly approved Azure region; no deployment default."
}

variable "storage_name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_name))
    error_message = "Use a globally unique, 3-24 character lowercase alphanumeric name."
  }
}

resource "azurerm_resource_group" "archive" {
  name     = "rg-${var.storage_name}"
  location = var.location
  tags     = { project = "revenue-pipeline", purpose = "synthetic-portfolio" }
}

resource "azurerm_storage_account" "archive" {
  name                            = var.storage_name
  resource_group_name             = azurerm_resource_group.archive.name
  location                        = azurerm_resource_group.archive.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true
  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "raw" {
  name                  = "raw"
  storage_account_id    = azurerm_storage_account.archive.id
  container_access_type = "private"
}

resource "azurerm_user_assigned_identity" "ingest" {
  name                = "id-${var.storage_name}-ingest"
  resource_group_name = azurerm_resource_group.archive.name
  location            = azurerm_resource_group.archive.location
}

resource "azurerm_role_assignment" "ingest" {
  scope                = azurerm_storage_container.raw.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ingest.principal_id
}

output "storage_account_id" {
  value = azurerm_storage_account.archive.id
}

output "ingest_identity_id" {
  value = azurerm_user_assigned_identity.ingest.id
}
