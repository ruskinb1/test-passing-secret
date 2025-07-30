const core = require('@actions/core');

try {
  const secretValue = core.getInput('secret_value', { required: true });
  core.info(`The secret value stored in Repository B is: ${secretValue}`);
} catch (error) {
  core.setFailed(`Action failed with error: ${error.message}`);
}
