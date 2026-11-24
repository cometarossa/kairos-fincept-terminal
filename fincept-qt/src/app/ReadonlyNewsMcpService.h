#pragma once
// Original Fincept F2: deliberately minimal read-only news MCP process.
// Separate from the GUI startup, broker services and finite QA selftest.
namespace fincept::app {
int run_readonly_news_mcp_service(int argc, char* argv[]);
}
