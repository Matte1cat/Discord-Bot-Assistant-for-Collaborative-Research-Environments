# Discord Bot Assistant for Collaborative Research Environments

Bachelor thesis project developed in Python using `discord.py`.

The project implements a modular Discord bot designed to support collaborative research environments.

The current prototype focuses on **service and infrastructure monitoring**, providing manual and periodic availability checks, runtime service management, transition detection, Discord notifications, persistent monitoring history, role-based administration, and containerized deployment.

> **Project status:** the monitoring-focused implementation is feature-complete. Automated and functional validation has been completed, and the project is in the final thesis-documentation and review stage.
>
> The system has been tested locally, through Docker, across multiple Discord guilds, and in a remote deployment environment.

---

## Features

The current implementation supports:

* Modular Discord bot architecture based on Cogs.
* HTTP-based monitoring checks.
* Manual service checks through `/status`.
* Periodic automatic monitoring.
* Runtime service states:

  * `UP`
  * `DOWN`
  * `ERROR`
* Aggregate service status based on multiple checks.
* Runtime tracking of the latest automatic monitoring result.
* Detection of service status transitions.
* Discord notifications for failures and recoveries.
* Multiple Discord alert destinations.
* Guild-specific alert channels.
* Dynamic service management directly from Discord.
* Dynamic addition and removal of monitoring checks.
* Guild-specific service-management roles.
* Persistent monitoring history using JSON Lines files.
* Persistent transition history.
* Bounded history files with automatic retention.
* Runtime configuration commands.
* Persistent operational configuration.
* Automatic initialization of deployment configuration from versioned templates.
* Structured console and rotating-file logging.
* Docker-based deployment.
* Support for development-guild and global Discord application-command synchronization.
* Automated tests for the main monitoring, configuration and persistence components.

Manual `/status` checks are intentionally separate from automatic monitoring: they do not update the automatic monitoring state, generate transitions, or enter the persistent monitoring history.

---

## Architecture Overview

The project separates the Discord-facing interface from the monitoring core.

```text
Discord
   │
   ├── General commands
   ├── Monitoring commands
   ├── Service administration
   └── Runtime configuration
            │
            ▼
     Monitoring Manager
            │
            ▼
      Configured Services
            │
            ▼
       Monitoring Checks
            │
            ▼
       Service Results
            │
      ┌─────┴─────┐
      ▼           ▼
Runtime State   Persistent History
      │
      ▼
Transition Detection
      │
      ▼
Discord Notifications
```

The monitoring layer does not depend on Discord command handling.

Discord Cogs act as an interface to application components such as the monitoring manager, service configuration store, runtime configuration store and history layer.

In particular, the Discord administration layer does not implement monitoring checks directly. It collects and validates user input, persists configuration, and uses the same check factory used during application startup to construct monitoring components.

This avoids maintaining separate monitoring implementations for JSON configuration and Discord-created services.

The separation also means that components such as:

* the scheduler;
* transition detection;
* history persistence;
* status aggregation;
* notification processing;

operate independently from the concrete type of monitoring check being executed.

---

## Project Structure

```text
.
├── resources/
│   ├── services.json
│   └── runtime.json
│
├── src/
│   └── main/
│       ├── alerts/
│       │   ├── base.py
│       │   └── discord_notifier.py
│       │
│       ├── cogs/
│       │   ├── general.py
│       │   ├── monitoring.py
│       │   ├── service_admin.py
│       │   └── config_admin.py
│       │
│       ├── history/
│       │   ├── base.py
│       │   ├── file_store.py
│       │   └── models.py
│       │
│       ├── monitoring/
│       │   ├── checks/
│       │   │   ├── base.py
│       │   │   ├── factory.py
│       │   │   └── http_check.py
│       │   ├── manager.py
│       │   ├── models.py
│       │   ├── scheduler.py
│       │   ├── service.py
│       │   ├── service_config_store.py
│       │   ├── service_loader.py
│       │   ├── state_store.py
│       │   └── transition_detector.py
│       │
│       ├── bootstrap.py
│       ├── bot.py
│       ├── config.py
│       ├── logging_config.py
│       ├── main.py
│       ├── runtime_config.py
│       ├── runtime_config_loader.py
│       └── runtime_config_store.py
│
├── tests/
│   ├── history/
│   └── monitoring/
│
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

Main responsibilities:

* `cogs/`: Discord commands, interactions, permissions and administration.
* `monitoring/`: service definitions, checks, scheduling, state tracking and transition detection.
* `monitoring/checks/`: common check abstraction, concrete monitoring implementations and check factory.
* `alerts/`: transition notification backends.
* `history/`: persistent monitoring history.
* `resources/`: versioned configuration templates.
* `bootstrap.py`: initialization of mutable operational configuration.
* `runtime_config_store.py`: safe persistent runtime configuration updates.
* `service_config_store.py`: safe persistent monitored-service configuration updates.

---

## Reference Environment

The final Docker and remote-deployment validation was performed using Python 3.12 and the following dependency versions available during the final validation period:

| Component      | Version |
| -------------- | ------- |
| Python         | 3.12    |
| discord.py     | 2.7.1   |
| aiohttp        | 3.14.3  |
| python-dotenv  | 1.2.3   |
| pytest         | 9.1.1   |
| pytest-asyncio | 1.4.0   |

The Docker image is based on:

```text
python:3.12-slim
```

`requirements.txt` and `requirements-dev.txt` currently specify dependency names rather than fixed package versions.

The table above therefore documents the reference environment used during the final project validation in September 2026.

---

## Installation

A Python virtual environment is recommended for local development.

Install runtime dependencies:

```powershell
pip install -r requirements.txt
```

Install development and testing dependencies:

```powershell
pip install -r requirements-dev.txt
```

---

## Environment Configuration

Create a `.env` file in the project root.

Only `BOT_TOKEN` is strictly required.

A recommended local development configuration is:

```env
BOT_TOKEN=your_discord_bot_token

LOG_LEVEL=INFO

SERVICES_CONFIG_PATH=instance/config/services.json
RUNTIME_CONFIG_PATH=instance/config/runtime.json

DISCORD_TEST_GUILD_ID=your_test_guild_id
```

### Available environment variables

| Variable                | Required | Description                                                    |
| ----------------------- | -------- | -------------------------------------------------------------- |
| `BOT_TOKEN`             | Yes      | Discord bot token.                                             |
| `LOG_LEVEL`             | No       | Application logging level. Defaults to `INFO`.                 |
| `DISCORD_TEST_GUILD_ID` | No       | Enables development-guild application-command synchronization. |
| `SERVICES_CONFIG_PATH`  | No       | Overrides the monitored-services configuration path.           |
| `RUNTIME_CONFIG_PATH`   | No       | Overrides the runtime configuration path.                      |

Supported `LOG_LEVEL` values are:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

### Development vs deployment command synchronization

When `DISCORD_TEST_GUILD_ID` is configured, application commands are copied and synchronized to the selected development guild.

This is useful during development because guild-specific command changes are normally visible faster.

When `DISCORD_TEST_GUILD_ID` is absent, the bot performs global application-command synchronization.

Global commands are therefore available to every Discord guild where the bot is installed.

Production or remote deployments should normally **not** define `DISCORD_TEST_GUILD_ID`.

The `.env` file may contain sensitive information and must not be committed to Git.

---

## Configuration Model

The project distinguishes between:

1. **versioned configuration templates**;
2. **mutable operational configuration**.

### Versioned templates

The repository contains:

```text
resources/
├── services.json
└── runtime.json
```

These files provide clean defaults for a new installation.

They are intended to act as templates rather than as mutable deployment state.

### Local operational configuration

The recommended local setup uses:

```text
instance/
└── config/
    ├── services.json
    └── runtime.json
```

with:

```env
SERVICES_CONFIG_PATH=instance/config/services.json
RUNTIME_CONFIG_PATH=instance/config/runtime.json
```

`instance/` is ignored by Git.

This prevents local guild IDs, role IDs, alert channels and runtime-created services from modifying the versioned templates.

### Automatic bootstrap

When a custom configuration path is provided through the environment but its target file does not yet exist, the startup bootstrap:

1. locates the corresponding versioned template;
2. creates the required target directory;
3. copies the template to the configured operational path;
4. continues startup using the newly created operational file.

Existing operational configuration is **never overwritten** by the bootstrap.

Application settings are loaded before the bootstrap step, so custom configuration paths defined in `.env` are available when missing operational files are initialized.

Conceptually:

```text
resources/services.json
        │
        │ first startup only
        ▼
instance/config/services.json
        │
        ▼
mutable runtime configuration
```

The same mechanism is used for `runtime.json`.

This allows both local and remote deployments to initialize themselves automatically while keeping application source configuration separate from deployment-specific state.

---

## Service Configuration

A service represents an entity that should be monitored.

Each service contains one or more checks describing how its availability should be evaluated.

Example:

```json
{
  "services": [
    {
      "key": "unimore",
      "display_name": "UniMORE Website",
      "checks": [
        {
          "type": "http",
          "name": "Website availability",
          "url": "https://www.unimore.it/",
          "expected_status": 200,
          "timeout_seconds": 5.0
        }
      ]
    }
  ]
}
```

A service therefore defines **what** is monitored, while each check defines **how** it is evaluated.

The same service may contain multiple checks.

For example, a future service could theoretically contain several independent checks covering different endpoints or protocols while still producing a single aggregate `ServiceResult`.

The current implementation provides the `http` check type.

An HTTP check supports:

* URL;
* expected HTTP status code;
* timeout;
* response-time measurement.

Unexpected HTTP status codes, request timeouts and HTTP client errors result in a `DOWN` status.

Unexpected internal exceptions are isolated by the monitoring manager and represented as `ERROR`.

---

## Extensible Monitoring Check Architecture

Monitoring checks are designed as interchangeable components.

The core architecture can be summarized as:

```text
BaseCheck
   │
   ├── HTTPCheck
   ├── FutureCheckA
   └── FutureCheckB
          │
          ▼
      Check Factory
          │
          ▼
        Service
          │
          ▼
   MonitoringManager
          │
          ▼
      Scheduler
```

All check implementations share the common `BaseCheck` interface and return the same `CheckResult` model.

The monitoring manager therefore does not need to know whether a result came from an HTTP request or from another future monitoring mechanism.

Likewise, the scheduler simply asks the manager to evaluate services and works with normalized `ServiceResult` objects.

### Check factory

Check creation is centralized in:

```text
monitoring/checks/factory.py
```

The factory maintains a registry that maps configuration type names to check builders.

Conceptually:

```text
"http" → HTTP check builder → HTTPCheck
```

When service configuration is loaded, the application:

```text
JSON check configuration
        ↓
build_check(...)
        ↓
type lookup in registry
        ↓
check-specific builder
        ↓
BaseCheck implementation
```

This provides one common construction path for monitoring checks.

The same `build_check()` mechanism is also used when a new service or check is created interactively from Discord.

### Adding a new core check type

A new monitoring mechanism can therefore be introduced without modifying the scheduler or monitoring manager.

Conceptually, adding a new core check requires:

```text
1. Implement a new BaseCheck subclass
                ↓
2. Implement its configuration builder
                ↓
3. Register the builder in the check factory
                ↓
4. The service loader can instantiate the new check
                ↓
5. Existing manager/scheduler/history logic continues unchanged
```

For example, a future implementation could introduce:

```text
"tcp" → TCPCheck
```

or another protocol-specific check while continuing to use the same:

* `CheckResult`;
* `ServiceResult`;
* status aggregation;
* scheduler;
* transition detection;
* history persistence;
* notification pipeline.

These additional check types are examples of possible extensions and are not implemented in the current prototype.

---

## Core Support vs Discord Configuration

Support in the monitoring core and interactive configuration through Discord are intentionally separated.

A check type registered in the factory can be supported by the monitoring subsystem and loaded from configuration.

For a check type to also be created interactively through Discord, the Discord administration layer must provide an appropriate user-input flow.

Currently:

```text
HTTP
├── supported by monitoring core
└── configurable directly from Discord
```

The distinction is exposed by `/service check-types`.

This avoids coupling the monitoring architecture to Discord UI requirements.

A future check type could therefore first be implemented at the monitoring-core level and later receive a Discord configuration interface without requiring changes to the scheduler or other monitoring components.

---

## Adding Services and Checks from Discord

Services do not have to be added manually by editing JSON files.

The bot provides interactive Discord commands for service administration.

### Creating a service

The `/service add` command first collects:

* service key;
* display name;
* check type.

For the currently implemented HTTP type, Discord then opens a modal requesting:

* check name;
* URL;
* expected HTTP status;
* timeout.

The flow is:

```text
/service add
      ↓
basic service information
      ↓
HTTP configuration modal
      ↓
input normalization
      ↓
check factory validation
      ↓
persistent services.json update
      ↓
MonitoringManager registration
      ↓
service available immediately
```

### Adding a check to an existing service

`/service check-add` follows a similar process:

```text
/service check-add
        ↓
select service and check type
        ↓
HTTP configuration modal
        ↓
factory validation
        ↓
persistent configuration update
        ↓
new immutable Service instance
        ↓
MonitoringManager replacement
        ↓
new check active immediately
```

This means checks created interactively and checks loaded at startup are constructed using the same monitoring factory and validation logic.

### Persistence before runtime mutation

Configuration changes follow a persistence-first approach.

The intended order is:

```text
Validate
   ↓
Persist configuration
   ↓
Update in-memory monitoring state
```

This reduces the risk of reporting a successful live configuration that would disappear on restart.

If persistence succeeds but a later live activation step fails, the persisted configuration remains available and will be loaded during the next application startup.

---

## Runtime Configuration

The default runtime template contains settings for automatic monitoring, history, alerts and service-management permissions.

```json
{
  "monitoring": {
    "interval_seconds": 60.0
  },
  "history": {
    "enabled": true,
    "directory": "data/history",
    "max_file_size_mb": 25
  },
  "alerts": {
    "discord": {
      "enabled": false,
      "destinations": []
    }
  },
  "service_management": {
    "guilds": []
  }
}
```

### Monitoring

```json
"monitoring": {
  "interval_seconds": 60.0
}
```

Controls the delay between automatic monitoring cycles.

### History

```json
"history": {
  "enabled": true,
  "directory": "data/history",
  "max_file_size_mb": 25
}
```

Controls:

* whether history persistence is enabled;
* the history storage directory;
* the maximum size of each history JSONL file.

### Discord alerts

```json
"alerts": {
  "discord": {
    "enabled": false,
    "destinations": []
  }
}
```

Each Discord guild may configure one alert destination.

### Service-management permissions

```json
"service_management": {
  "guilds": []
}
```

Guild configuration is created automatically when the bot joins or detects a Discord server.

Each guild can contain its own list of authorized service-management role IDs.

Discord server Administrators remain authorized regardless of this list.

---

## Running Locally

From the project root:

```powershell
python src\main\main.py
```

With the recommended `.env` configuration, the application uses:

```text
instance/config/services.json
instance/config/runtime.json
```

instead of modifying the versioned files under `resources/`.

During startup, the bot initializes:

```text
Environment configuration
        ↓
Configuration bootstrap
        ↓
HTTP client session
        ↓
Monitored services
        ↓
Runtime configuration
        ↓
History persistence
        ↓
Alert destinations
        ↓
Monitoring scheduler
        ↓
Discord Cogs
        ↓
Application-command synchronization
```

---

## Discord Commands

## General Commands

### `/ping`

Checks whether the bot is responsive and displays its Discord latency.

### `/about`

Displays general information about the project and bot.

---

## Monitoring Commands

### `/status`

Runs an immediate manual monitoring check for a selected service.

Example:

```text
/status service:unimore
```

Manual checks:

* do not modify automatic monitoring state;
* do not generate transitions;
* are not persisted in monitoring history.

### `/history`

Displays recent automatically collected monitoring results and recent state transitions.

Example:

```text
/history service:unimore limit:5
```

The supported result limit is between 1 and 10 entries.

---

## Service Administration

Service-management mutation commands require either:

* Discord server Administrator permission; or
* a role explicitly authorized for that guild.

### `/service list`

Lists configured monitored services and their checks.

### `/service check-types`

Lists monitoring check types registered in the application.

The command also indicates whether a check type can currently be configured directly through Discord or is only available to the monitoring core.

### `/service add`

Adds a new monitored service.

The command collects the basic service information and opens the appropriate check-configuration interface.

For HTTP checks this is a Discord modal.

The resulting configuration is validated, persisted and activated immediately.

### `/service delete`

Removes a monitored service from persistent configuration and from the active monitoring manager.

Its current in-memory monitoring state is also removed.

### `/service check-add`

Adds a monitoring check to an existing service.

The updated service definition is persisted and then activated by replacing the immutable service instance in the monitoring manager.

### `/service check-delete`

Removes a monitoring check from an existing service.

A service must always contain at least one check.

The final check therefore cannot be removed individually; the entire service must be deleted instead.

### `/service manager-role-add`

Authorizes a Discord role to manage monitored services and selected runtime configuration.

This command requires Administrator permission.

The `@everyone` role and managed integration/bot roles cannot be configured as service-management roles.

### `/service manager-role-delete`

Removes a previously authorized service-management role.

This command requires Administrator permission.

### `/service manager-role-list`

Lists service-management roles configured for the current guild.

---

## Runtime Configuration Commands

Runtime configuration commands use the same service-management permission model.

### `/config show`

Displays selected persisted configuration values, including:

* monitoring interval;
* history enabled state;
* history directory;
* Discord alerts enabled state;
* total configured alert destinations;
* alert channel configured for the current guild.

### `/config monitoring-interval`

Persists a new automatic monitoring interval.

Accepted values:

```text
1 - 86400 seconds
```

The bot must be restarted before the existing scheduler is reconstructed using the new interval.

### `/config history-enabled`

Enables or disables persistent monitoring history.

The value is persisted immediately.

A restart is required because the history store is initialized during application startup.

### `/config alerts-enabled`

Enables or disables Discord transition notifications.

The global enabled state is persisted immediately but requires a restart to reconstruct the alert-notifier lifecycle.

Alerts cannot be enabled when no Discord alert destinations are configured.

### `/config alert-channel`

Sets the transition-notification channel for the current Discord guild.

If Discord alerts are already active, the destination change is applied immediately without restarting the application.

### `/config alert-channel-clear`

Removes the alert destination configured for the current guild.

The change is applied immediately.

If the removed channel was the final configured destination, Discord alerts are automatically disabled in persistent configuration.

---

## Multi-Guild Behaviour

A single bot instance can be installed in multiple Discord guilds.

The current prototype intentionally follows a **shared monitored infrastructure model**.

### Shared application state

The following are shared by every guild connected to the same bot instance:

* monitored services;
* monitoring checks;
* monitoring interval;
* scheduler;
* monitoring history;
* service runtime state;
* detected transitions.

### Guild-specific state

The following are isolated by Discord guild:

* authorized service-management roles;
* Discord alert destination.

Conceptually:

```text
                Shared infrastructure
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
     Discord Guild A          Discord Guild B
     - Role A                  - Role B
     - Alert Channel A         - Alert Channel B
```

Multiple Discord servers therefore act as different interfaces to the same monitored infrastructure.

This is intentionally different from a fully isolated multi-tenant architecture where every guild would have an independent service catalogue and monitoring scheduler.

Per-guild monitored infrastructures are outside the scope of the current prototype.

---

## Automatic Monitoring

The monitoring scheduler periodically evaluates every registered service.

```text
Configured Service
       ↓
Monitoring Check(s)
       ↓
Service Result
       ↓
Persistent History
       ↓
Runtime State
       ↓
Transition Detection
       ↓
Discord Alert
```

Checks belonging to the same service are executed asynchronously.

The resulting check statuses are aggregated into one service status.

### Aggregate service status

For services containing multiple checks, the overall result follows the priority:

```text
ERROR > DOWN > UP
```

Therefore:

* if any check reports `ERROR`, the service is `ERROR`;
* otherwise, if any check reports `DOWN`, the service is `DOWN`;
* the service is `UP` only when every check is `UP`.

This keeps individual check details while still providing one high-level service state.

---

## Transition Detection

Only changes between consecutive automatic monitoring results are considered transitions.

The first result observed after startup establishes the baseline state and does not generate an alert.

Example:

```text
Initial state → UP       no alert
UP → UP                  no alert
UP → DOWN                alert
DOWN → DOWN              no repeated alert
DOWN → UP                recovery alert
```

Possible transitions include:

```text
UP → DOWN
DOWN → UP
UP → ERROR
ERROR → UP
DOWN → ERROR
ERROR → DOWN
```

Notifications are therefore event-based rather than being repeatedly generated for an unchanged failure state.

---

## Failure Isolation

Monitoring components are designed so that failures in optional or individual operations do not unnecessarily terminate the whole monitoring scheduler.

Examples include:

* unexpected exceptions inside an individual check;
* history persistence errors;
* notification-delivery errors.

Unexpected check failures are converted into `ERROR` results where possible.

History and notification errors are logged and isolated from subsequent monitoring operations.

A failure in one service check therefore does not prevent unrelated services from continuing to be monitored.

---

## Monitoring History

Automatic monitoring results are persisted as JSON Lines files:

```text
data/
└── history/
    ├── service_results.jsonl
    └── transitions.jsonl
```

### `service_results.jsonl`

Contains periodic service results including:

* service key;
* service display name;
* aggregate status;
* individual check results;
* check timestamps;
* response times;
* result details.

### `transitions.jsonl`

Contains detected service state changes.

Example:

```text
UP → DOWN
DOWN → UP
UP → ERROR
ERROR → UP
```

Manual `/status` checks are intentionally excluded.

---

## History Retention

Each history file has its own configurable maximum size.

The default configuration is:

```text
25 MiB per history file
```

When a file grows beyond its configured maximum:

1. complete JSONL records are read;
2. the oldest records are discarded;
3. the newest records are retained;
4. the file is reduced to approximately 80% of the configured limit;
5. the retained data atomically replaces the previous file.

The service-results and transition files are bounded independently.

With the default configuration, the theoretical combined history size is approximately:

```text
50 MiB
```

before trimming reduces whichever file crosses its individual threshold.

Complete lines are retained during trimming so the remaining file continues to contain valid JSONL records.

Malformed history records encountered during reading are ignored and logged instead of preventing access to valid entries.

---

## Logging

Application logging is written both to:

* the process console (`stderr`);
* rotating log files.

Local log files are stored under:

```text
logs/
```

The rotating file logger uses:

```text
Maximum active file size: 5 MiB
Backup files:             3
```

Log records include contextual information such as:

* service key;
* monitoring check.

The log level is configured through:

```env
LOG_LEVEL=INFO
```

Possible levels are:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Standard output is particularly useful in containerized and remote environments where the deployment platform collects process logs directly.

---

## Docker Deployment

The project includes a Dockerfile based on:

```dockerfile
FROM python:3.12-slim
```

The bot is a long-running Python process and does **not** expose an HTTP web application.

No inbound web port is required.

Communication is outbound:

```text
Discord Bot Process
      │
      ├──→ Discord API / Gateway
      │
      └──→ monitored HTTP services
```

The Dockerfile therefore does not require an `EXPOSE` directive.

### Docker Compose

The provided `compose.yaml`:

* builds the application image;
* loads the `.env` file;
* stores mutable configuration outside the image;
* persists monitoring history;
* persists local log files;
* automatically restarts the container unless explicitly stopped.

Inside the local Docker deployment:

```text
/app/config/services.json
/app/config/runtime.json
/app/data/history/
/app/logs/
```

are mapped from:

```text
instance/config/ → /app/config
data/            → /app/data
logs/            → /app/logs
```

Start or rebuild:

```powershell
docker compose up -d --build
```

Inspect the container:

```powershell
docker compose ps
```

Inspect logs:

```powershell
docker compose logs
```

Stop the deployment:

```powershell
docker compose down
```

Application-code or dependency changes require rebuilding the image.

Changes to configuration values whose runtime components are created only during startup require restarting the container.

---

## Remote Deployment

The container can also run on services capable of hosting long-running workers or containers.

The final project validation included a remote deployment using **Railway**.

Railway builds the application directly from the repository `Dockerfile`; the local `compose.yaml` is not required by the remote platform.

The bot does not require Railway public HTTP networking or a public domain because it initiates outbound connections rather than accepting incoming web requests.

### Persistent Railway storage

During final validation, one Railway persistent volume was mounted at:

```text
/app/data
```

The remote environment used:

```env
SERVICES_CONFIG_PATH=/app/data/config/services.json
RUNTIME_CONFIG_PATH=/app/data/config/runtime.json
```

The resulting persistent structure is:

```text
/app/data/
├── config/
│   ├── services.json
│   └── runtime.json
│
└── history/
    ├── service_results.jsonl
    └── transitions.jsonl
```

On the first deployment the volume is empty, so the startup bootstrap automatically initializes the two configuration files using the repository templates.

Later deployments preserve the existing operational configuration because the bootstrap never overwrites existing files.

### Remote validation

The deployment was validated by:

* starting the bot from the repository Dockerfile;
* synchronizing global Discord application commands;
* executing Discord commands against the remote bot;
* performing outbound HTTP monitoring;
* detecting real remote service status changes;
* delivering transition and recovery notifications;
* adding a monitored service from Discord;
* redeploying the application;
* confirming that the newly added service survived the redeployment;
* deleting the service;
* redeploying again;
* confirming that the deletion also persisted.

This validated both the application container and its persistent operational configuration.

---

## Tests

Automated tests can be executed from the project root with:

```powershell
pytest -q
```

During the final validation stage:

```text
97 tests passed
```

The automated test suite covers, among other areas:

* HTTP monitoring checks;
* expected HTTP status handling;
* request timeouts and client errors;
* monitoring manager behaviour;
* aggregate service state;
* unexpected-check failure isolation;
* service registration;
* service replacement;
* service removal;
* service configuration loading;
* service configuration persistence;
* runtime configuration loading and validation;
* runtime configuration persistence;
* guild-specific configuration parsing;
* management-role configuration;
* transition detection;
* scheduler behaviour;
* notification failure isolation;
* monitoring history persistence;
* history retrieval;
* history ordering;
* malformed history records;
* history filtering;
* history retention and file trimming;
* startup configuration bootstrap from `.env`;
* startup with configuration paths already present in the process environment;
* preservation of existing operational configuration during bootstrap.

The main automated suite relies on temporary files, mocks and local test doubles where appropriate and does not require real Internet services.

---

## Final Manual Validation

In addition to the automated test suite, the application has been manually validated through:

* normal local Python execution;
* local configuration bootstrap;
* Docker Desktop;
* Docker persistent bind mounts;
* service creation from Discord;
* service deletion;
* check creation;
* check deletion;
* runtime configuration commands;
* configuration persistence after restart;
* monitoring history persistence;
* history file retention behaviour;
* Discord alert destination changes;
* transition notification delivery;
* recovery notification delivery;
* two separate Discord guilds;
* guild-specific service-management role isolation;
* guild-specific alert destinations;
* global application-command synchronization;
* remote Docker deployment;
* persistent remote configuration across redeployments.

---

## Design Decisions and Current Limitations

### HTTP monitoring scope

The current implementation provides HTTP availability checks.

The check architecture is intentionally extensible, but additional protocols are outside the implemented prototype scope.

---

### File-based persistence

JSON is used for operational configuration and JSONL for monitoring history.

This was intentionally chosen instead of introducing a database during the current prototype.

The history layer is accessed through an abstraction, allowing a different persistence implementation to replace the file-based store in a future version.

---

### Runtime monitoring state is not restored after restart

Monitoring history is persistent, but the latest automatic `MonitoringStateStore` is maintained in memory.

After application restart, the first automatic result for each service therefore becomes a new baseline and does not generate a transition.

For example, if a service was previously `UP` and the bot restarts while that service is already `DOWN`, the first new `DOWN` result establishes the baseline rather than generating an `UP → DOWN` notification.

Persistent state reconstruction from history could be introduced in future work if required.

---

### Shared monitored infrastructure

Services and general monitoring configuration are shared by every Discord guild connected to the same bot instance.

Authorization roles and notification destinations are guild-specific.

A fully independent multi-tenant architecture with separate service catalogues per guild is outside the current prototype scope.

---

### Selected runtime settings require restart

Changes to:

* monitoring interval;
* history enabled state;
* global Discord alerts enabled state;

are persisted immediately but require application restart before the corresponding runtime components are reconstructed using the new configuration.

Alert-channel destination changes can instead be applied live.

---

### File-based history is optimized for prototype-scale use

History files have bounded storage and are sufficient for the current monitoring prototype.

Reads currently operate over file-based JSONL history rather than through an indexed query engine.

For significantly larger monitoring environments, a structured database or dedicated monitoring backend would provide more scalable querying and analytics.

---

## Possible Future Extensions

Possible future extensions include:

* additional monitoring check types;
* database-backed persistence;
* persisted runtime-state restoration;
* independent monitored infrastructures per Discord guild;
* additional monitoring statistics and reporting;
* configurable monitoring intervals per service or check;
* remote server-management operations;
* stronger integration with research infrastructure;
* institutional authentication or identity-system integration.

These possibilities are architectural extensions rather than requirements of the current implemented monitoring prototype.

---

## Thesis Context

This repository was developed as part of a Bachelor's thesis project at the **University of Modena and Reggio Emilia (UniMORE)**.

The project investigates the use of Discord as the interface for a modular assistant supporting collaborative research environments.

The implemented prototype focuses on infrastructure monitoring and demonstrates:

* modular Discord integration;
* separation between interface and monitoring logic;
* extensible check construction through a registry-based factory;
* asynchronous service monitoring;
* multi-check service aggregation;
* automatic transition detection;
* persistent monitoring data;
* bounded file-based history;
* configurable Discord notification delivery;
* role-based administration;
* runtime service configuration from Discord;
* runtime configuration management;
* multi-guild operation;
* local and containerized execution;
* persistent remote deployment.
