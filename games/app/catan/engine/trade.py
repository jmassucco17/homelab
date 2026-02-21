"""Catan trading logic.

Handles bank trades (4:1, 3:1 generic harbor, 2:1 specific harbor),
player-to-player trade offer/accept/reject lifecycle, and trade validation.
"""

from __future__ import annotations

import enum
import uuid

import pydantic

from games.app.catan.models.actions import TradeOffer
from games.app.catan.models.board import PortType, ResourceType
from games.app.catan.models.game_state import GamePhase, GameState
from games.app.catan.models.player import Player, Resources


class TradeStatus(enum.StrEnum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'


class PendingTrade(pydantic.BaseModel):
    trade_id: str
    offering_player: int
    offering: dict[str, int]
    requesting: dict[str, int]
    target_player: int | None
    accepted_by: list[int] = pydantic.Field(default_factory=lambda: [])
    rejected_by: list[int] = pydantic.Field(default_factory=lambda: [])
    status: TradeStatus = TradeStatus.PENDING


def get_bank_trade_ratio(resource: ResourceType, player: Player) -> int:
    specific_port = PortType(resource.value)
    if specific_port in player.ports_owned:
        return 2
    if PortType.GENERIC in player.ports_owned:
        return 3
    return 4


def can_bank_trade(
    player: Player, giving: ResourceType, receiving: ResourceType
) -> tuple[bool, str]:
    if giving == receiving:
        return False, 'Cannot trade a resource for itself'
    ratio = get_bank_trade_ratio(giving, player)
    if player.resources.get(giving) < ratio:
        have = player.resources.get(giving)
        return False, f'Need {ratio} {giving} to bank trade, have {have}'
    return True, ''


def apply_bank_trade(
    player: Player, giving: ResourceType, receiving: ResourceType
) -> Player:
    ratio = get_bank_trade_ratio(giving, player)
    new_resources = player.resources.subtract({giving.value: ratio}).add(
        Resources(**{receiving.value: 1})
    )
    return player.model_copy(update={'resources': new_resources})


def can_port_trade(
    player: Player, giving: ResourceType, giving_count: int, receiving: ResourceType
) -> tuple[bool, str]:
    if giving == receiving:
        return False, 'Cannot trade a resource for itself'
    specific_port = PortType(giving.value)
    if giving_count == 2 and specific_port not in player.ports_owned:
        return False, f'Need a {giving} port to trade 2:1'
    if giving_count == 3 and PortType.GENERIC not in player.ports_owned:
        return False, 'Need a generic port to trade 3:1'
    if giving_count not in (2, 3):
        return False, f'Invalid giving_count {giving_count} for port trade'
    if player.resources.get(giving) < giving_count:
        have = player.resources.get(giving)
        return False, f'Need {giving_count} {giving}, have {have}'
    return True, ''


def apply_port_trade(
    player: Player, giving: ResourceType, giving_count: int, receiving: ResourceType
) -> Player:
    new_resources = player.resources.subtract({giving.value: giving_count}).add(
        Resources(**{receiving.value: 1})
    )
    return player.model_copy(update={'resources': new_resources})


def _resources_from_dict(d: dict[str, int]) -> Resources:
    return Resources(**{k: v for k, v in d.items() if v > 0})


def create_trade_offer(
    game_state: GameState, action: TradeOffer
) -> tuple[bool, str, PendingTrade | None]:
    if game_state.phase != GamePhase.MAIN:
        return False, 'Trades can only be made during the main phase', None
    if game_state.turn_state.player_index != action.player_index:
        return False, 'Only the active player can propose a trade', None
    player = game_state.players[action.player_index]
    if not player.resources.can_afford(action.offering):
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
    game_state: GameState, pending_trade: PendingTrade, accepting_player: int
) -> tuple[bool, str, GameState | None]:
    if pending_trade.status != TradeStatus.PENDING:
        return False, 'Trade is no longer pending', None
    offerer = game_state.players[pending_trade.offering_player]
    accepter = game_state.players[accepting_player]
    if not offerer.resources.can_afford(pending_trade.offering):
        return False, 'Offering player no longer has sufficient resources', None
    if not accepter.resources.can_afford(pending_trade.requesting):
        return False, 'Accepting player does not have sufficient resources', None

    new_offerer_resources = offerer.resources.subtract(pending_trade.offering).add(
        _resources_from_dict(pending_trade.requesting)
    )
    new_accepter_resources = accepter.resources.subtract(pending_trade.requesting).add(
        _resources_from_dict(pending_trade.offering)
    )

    new_players = list(game_state.players)
    new_players[pending_trade.offering_player] = offerer.model_copy(
        update={'resources': new_offerer_resources}
    )
    new_players[accepting_player] = accepter.model_copy(
        update={'resources': new_accepter_resources}
    )

    new_turn_state = game_state.turn_state.model_copy(update={'active_trade_id': None})
    new_state = game_state.model_copy(
        update={'players': new_players, 'turn_state': new_turn_state}
    )
    return True, '', new_state


def reject_trade(pending_trade: PendingTrade, rejecting_player: int) -> PendingTrade:
    new_rejected = list(pending_trade.rejected_by)
    if rejecting_player not in new_rejected:
        new_rejected.append(rejecting_player)
    return pending_trade.model_copy(update={'rejected_by': new_rejected})


def cancel_trade(pending_trade: PendingTrade) -> PendingTrade:
    return pending_trade.model_copy(update={'status': TradeStatus.CANCELLED})
