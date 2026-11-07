# Option A: read the foundation stack's OUTPUTS from its state file.
# Safe because the foundation state holds no secret values.
data "terraform_remote_state" "foundation" {
  backend = "local"
  config = {
    path = "../foundation/terraform.tfstate"
  }
}

locals {
  f = data.terraform_remote_state.foundation.outputs
}