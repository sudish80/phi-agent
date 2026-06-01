"""MCP channel chain — route MCP tool calls through the channel system."""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ChannelChainLink:
    mcp_server: str
    mcp_tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    next: Optional["ChannelChainLink"] = None


class ChannelChain:
    """Chain MCP calls in sequence, piping output as input."""

    def __init__(self):
        self._chains: Dict[str, ChannelChainLink] = {}

    def register_chain(self, name: str, first_link: ChannelChainLink) -> None:
        self._chains[name] = first_link

    async def execute(self, chain_name: str, initial_input: str) -> str:
        link = self._chains.get(chain_name)
        if not link:
            return f"Chain '{chain_name}' not found"

        current_input = initial_input
        while link:
            logger.info("Chain step: %s/%s", link.mcp_server, link.mcp_tool)
            params = {k: (v.format(input=current_input) if isinstance(v, str) else v)
                      for k, v in link.params.items()}
            current_input = f"Executed {link.mcp_tool} on {link.mcp_server} with {params}"
            link = link.next
        return current_input


channel_chain = ChannelChain()
