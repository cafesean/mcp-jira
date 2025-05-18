**Technical Solution: TS-JiraPATPerCall-001 - Implement Mandatory Per-Request PAT Authentication via Tool Input**

**Related Epic:** Enable Per-Request Authentication for Jira MCP Server
**Goal:** All authenticated Jira API interactions must use a PAT provided as a direct input parameter with each tool call. The `mcp-atlassian` server will not maintain a default Jira authentication configuration for API calls.

**Tasks:**

*   **Core Authentication & Client Infrastructure:**
    *   `- [ ] TS-JiraPATPerCall-01`: **Refactor `JiraConfig` (`jira/config.py`)**
        *   Remove environment variable loading and storage for default Jira PAT, username/API token, and OAuth credentials intended for *Jira API authentication*.
        *   Retain URL, SSL, and proxy configurations.
    *   `- [ ] TS-JiraPATPerCall-02`: **Refactor `JiraClient.__init__` (`jira/client.py`)**
        *   Remove initialization of a default authenticated `self.jira` (`atlassian.Jira`) instance. `self.jira` can be `None` or a similar non-authenticated placeholder.
    *   `- [ ] TS-JiraPATPerCall-03`: **Implement `_create_jira_client_with_pat` in `jira/client.py`**
        *   Method signature: `_create_jira_client_with_pat(self, pat: str) -> Jira`.
        *   Always instantiates a new `atlassian.Jira` client using the provided `pat`, `self.config.url`, `self.config.is_cloud`, `self.config.ssl_verify`.
        *   Applies SSL verification (via `configure_ssl_verification`) and proxy settings (from `self.config`) to the new client's session.
        *   Logs INFO "Creating Jira client for request using provided PAT." (PAT VALUE NOT LOGGED).
    *   `- [ ] TS-JiraPATPerCall-04`: **Update `get_paged` in `jira/client.py`**
        *   Change signature to require `pat: str`.
        *   Use `jira_for_call = self._create_jira_client_with_pat(pat)` for all API calls.

*   **MCP Tool Definitions (`servers/jira.py`):**
    *   `- [ ] TS-JiraPATPerCall-05`: **Update Jira Tool Signatures and Logic**
        *   For every tool requiring Jira authentication:
            *   Add mandatory input parameter: `jira_pat: Annotated[str, Field(description="Jira Personal Access Token for this request.", exclude=True)]`.
            *   Update tool docstring (Args section).
            *   Pass received `jira_pat` to the corresponding `JiraFetcher` method.

*   **JiraFetcher Mixin Adaptations (Propagate `pat` and use `_create_jira_client_with_pat`):**
    *   *General pattern for methods making API calls in all mixins:*
        1.  Modify signature to require `pat: str`.
        2.  Call `jira_for_call = self._create_jira_client_with_pat(pat)`.
        3.  Use `jira_for_call.api_method(...)` for Jira API interactions.
        4.  Propagate `pat` to internal helpers that make their own distinct API calls.
    *   `- [ ] TS-JiraPATPerCall-06`: Adapt `IssuesMixin` (`jira/issues.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-07`: Adapt `SearchMixin` (`jira/search.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-08`: Adapt `ProjectsMixin` (`jira/projects.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-09`: Adapt `CommentsMixin` (`jira/comments.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-10`: Adapt `EpicsMixin` (`jira/epics.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-11`: **Adapt `FieldsMixin` (`jira/fields.py`) methods**
        *   Remove global field caching (`_field_ids_cache`, `_field_name_to_id_map`). All field metadata methods (`get_fields`, `get_field_id`, etc.) will perform live API calls using the client derived from the provided `pat`.
    *   `- [ ] TS-JiraPATPerCall-12`: Adapt `LinksMixin` (`jira/links.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-13`: Adapt `SprintsMixin` (`jira/sprints.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-14`: Adapt `TransitionsMixin` (`jira/transitions.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-15`: **Adapt `UsersMixin` (`jira/users.py`) methods**
        *   `get_current_user_account_id()`: Must accept `pat: str` to identify the user for *that PAT*, or be removed if its original purpose (server's default identity) is obsolete.
        *   Other methods (`_get_account_id`, `get_user_profile_by_identifier`, etc.) must accept `pat: str`.
    *   `- [ ] TS-JiraPATPerCall-16`: Adapt `WorklogMixin` (`jira/worklog.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-17`: Adapt `AttachmentsMixin` (`jira/attachments.py`) methods.
    *   `- [ ] TS-JiraPATPerCall-18`: Adapt `BoardsMixin` (`jira/boards.py`) methods.

*   **Testing & Documentation:**
    *   `- [ ] TS-JiraPATPerCall-19`: **Write Unit/Integration Tests**
        *   Verify tools correctly use the `jira_pat` provided as a tool input.
        *   Test error handling for invalid/missing PATs passed as tool inputs.
        *   Confirm SSL/proxy settings apply to dynamically created clients.
    *   `- [ ] TS-JiraPATPerCall-20`: **Update Documentation (`README.md`, etc.)**
        *   Reflect mandatory `jira_pat` tool input parameter.
        *   Explain that the client (e.g., via `mcp-remote` reading its env) is expected to inject this `jira_pat` into tool inputs.
        *   Emphasize security implications for how clients manage and provide this PAT.
    *   `- [ ] TS-JiraPATPerCall-21`: **Security Review and Logging Audit**
        *   Ensure no PAT values (from tool inputs) are logged by `mcp-atlassian`.
        *   Confirm `exclude=True` for the `jira_pat` `Field` is effective.

---

This list should now accurately reflect the "PAT as a mandatory tool input parameter" approach, consistent with the client configuration you provided and the assumption that `mcp-remote` (or similar) will handle the injection of the `JIRA_PERSONAL_TOKEN` from its environment into the tool call's `inputs`.