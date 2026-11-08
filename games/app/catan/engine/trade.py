"""Catan trading logic.

Handles bank trades (4:1, 3:1 generic harbor, 2:1 specific harbor),
player-to-player trade offer/accept/reject lifecycle, and trade validation.
"""

from __future__ import annotations

import enum
import uuid

import pydantic

from games.app.catan.models import actions, board, game_state
from games.app.catan.models import player as player_module


class TradeStatus(enum.StrEnum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'


class PendingTrade(pydantic.BaseModel):
    """Represents an in-flight player-to-player trade offer."""

    trade_id: str
    offering_player: int
    offering: dict[str, int]
    requesting: dict[str, int]
    target_player: int | None
    accepted_by: list[int] = pydantic.Field(default_factory=lambda: [])
    rejected_by: list[int] = pydantic.Field(default_factory=lambda: [])
    status: TradeStatus = TradeStatus.PENDING


def get_bank_trade_ratio(
    resource: board.ResourceType, offering_player: player_module.Player
) -> int:
    """Return the number of cards the player must give for one card in return.

    Checks for a matching 2:1 specific-resource port first, then falls back to
    3:1 generic port, then the default 4:1 ratio.
    """
    # A specific-resource port (e.g. wood port) allows 2:1 for that resource.
    specific_port = board.PortType(resource.value)
    if specific_port in offering_player.ports_owned:
        return 2
    # A generic port allows 3:1 for any resource.
    if board.PortType.GENERIC in offering_player.ports_owned:
        return 3
    # No port: standard 4:1 bank trade.
    return 4


def can_bank_trade(
    offering_player: player_module.Player,
    giving: board.ResourceType,
    receiving: board.ResourceType,
) -> tuple[bool, str]:
    """Check whether a player can execute a bank trade.

    Returns (True, '') on success, or (False, reason) on failure.
    """
    if giving == receiving:
        return False, 'Cannot trade a resource for itself'
    required_ratio = get_bank_trade_ratio(giving, offering_player)
    current_amount = offering_player.resources.get(giving)
    if current_amount < required_ratio:
        return (
            False,
            f'Need {required_ratio} {giving} to bank trade, have {current_amount}',
        )
    return True, ''


def apply_bank_trade(
    offering_player: player_module.Player,
    giving: board.ResourceType,
    receiving: board.ResourceType,
) -> player_module.Player:
    """Execute a bank trade, returning an updated Player with resources exchanged."""
    required_ratio = get_bank_trade_ratio(giving, offering_player)
    # Subtract the cards given to the bank, then add the one card received.
    after_giving = offering_player.resources.subtract({giving.value: required_ratio})
    new_resources = after_giving.add(
        player_module.Resources().with_resource(receiving, 1)
    )
    return offering_player.model_copy(update={'resources': new_resources})


def can_port_trade(
    offering_player: player_module.Player,
    giving: board.ResourceType,
    giving_count: int,
    receiving: board.ResourceType,
) -> tuple[bool, str]:
    """Check whether a player can execute a port trade.

    Returns (True, '') on success, or (False, reason) on failure.
    """
    if giving == receiving:
        return False, 'Cannot trade a resource for itself'
    if giving_count not in (2, 3):
        return False, f'Invalid giving_count {giving_count} for port trade'
    # A 2:1 trade requires owning the specific-resource port for the given resource.
    specific_port = board.PortType(giving.value)
    if giving_count == 2 and specific_port not in offering_player.ports_owned:
        return False, f'Need a {giving} port to trade 2:1'
    # A 3:1 trade requires owning at least one generic port.
    if giving_count == 3 and board.PortType.GENERIC not in offering_player.ports_owned:
        return False, 'Need a generic port to trade 3:1'
    current_amount = offering_player.resources.get(giving)
    if current_amount < giving_count:
        return False, f'Need {giving_count} {giving}, have {current_amount}'
    return True, ''


def apply_port_trade(
    offering_player: player_module.Player,
    giving: board.ResourceType,
    giving_count: int,
    receiving: board.ResourceType,
) -> player_module.Player:
    """Execute a port trade, returning an updated Player with resources exchanged."""
    # Subtract the cards given to the port, then add the one card received.
    after_giving = offering_player.resources.subtract({giving.value: giving_count})
    new_resources = after_giving.add(
        player_module.Resources().with_resource(receiving, 1)
    )
    return offering_player.model_copy(update={'resources': new_resources})


def _resources_from_dict(resource_dict: dict[str, int]) -> player_module.Resources:
    """Convert a resource count dict (from a trade offer) into a Resources model."""
    return player_module.Resources(**{k: v for k, v in resource_dict.items() if v > 0})


def create_trade_offer(
    current_state: game_state.GameState, action: actions.TradeOffer
) -> tuple[bool, str, PendingTrade | None]:
    """Validate and create a pending trade offer from the active player.

    Returns (True, '', PendingTrade) on success, or (False, reason, None) on failure.
    """
    if current_state.phase != game_state.GamePhase.MAIN:
        return False, 'Trades can only be made during the main phase', None
    if current_state.turn_state.player_index != action.player_index:
        return False, 'Only the active player can propose a trade', None
    offering_player = current_state.players[action.player_index]
    if not offering_player.resources.can_afford(action.offering):
        return False, 'Insufficient resources to offer', None
    trade = PendingTrade(
        trade_id=str(uuid.uuid4()),
        offering_player=action.player_index,
        offering=action.offering,
        requesting=action.requesting,
        target_player=action.target_player,
    )
    return True, '', trade


def accept_trade(
    current_state: game_state.GameState,
    pending_trade: PendingTrade,
    accepting_player: int,
) -> tuple[bool, str, game_state.GameState | None]:
    """Execute an accepted trade, atomically transferring resources between players.

    Returns (True, '', new_GameState) on success, or (False, reason, None) on failure.
    """
    if pending_trade.status != TradeStatus.PENDING:
        return False, 'Trade is no longer pending', None
    offerer = current_state.players[pending_trade.offering_player]
    accepter = current_state.players[accepting_player]
    # Re-validate both sides still have the required resources at acceptance time.
    if not offerer.resources.can_afford(pending_trade.offering):
        return False, 'Offering player no longer has sufficient resources', None
    if not accepter.resources.can_afford(pending_trade.requesting):
        return False, 'Accepting player does not have sufficient resources', None

    # Transfer resources: offerer gives their offer and receives the request;
    # accepter does the reverse.
    new_offerer_resources = offerer.resources.subtract(pending_trade.offering).add(
        _resources_from_dict(pending_trade.requesting)
    )
    new_accepter_resources = accepter.resources.subtract(pending_trade.requesting).add(
        _resources_from_dict(pending_trade.offering)
    )

    new_players = list(current_state.players)
    new_players[pending_trade.offering_player] = offerer.model_copy(
        update={'resources': new_offerer_resources}
    )
    new_players[accepting_player] = accepter.model_copy(
        update={'resources': new_accepter_resources}
    )

    # Clear the active trade once it completes.
    new_turn_state = current_state.turn_state.model_copy(
        update={'active_trade_id': None}
    )
    new_state = current_state.model_copy(
        update={'players': new_players, 'turn_state': new_turn_state}
    )
    return True, '', new_state


def reject_trade(pending_trade: PendingTrade, rejecting_player: int) -> PendingTrade:
    """Record a player's rejection of the trade offer (idempotent)."""
    updated_rejected_by = list(pending_trade.rejected_by)
    if rejecting_player not in updated_rejected_by:
        updated_rejected_by.append(rejecting_player)
    return pending_trade.model_copy(update={'rejected_by': updated_rejected_by})


def cancel_trade(pending_trade: PendingTrade) -> PendingTrade:
    """Cancel a pending trade offer, marking it as CANCELLED."""
    return pending_trade.model_copy(update={'status': TradeStatus.CANCELLED})
