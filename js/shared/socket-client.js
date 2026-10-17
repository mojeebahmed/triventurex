/**
 * socket-client.js
 * Shared Socket.IO client abstraction for Triventurex V2.
 * Always included in pages but safely no-ops if io is undefined
 * (i.e. when served via file:// or python http.server without Socket.IO).
 */

const TX_NET = (() => {
  let _socket   = null;
  let _gameId   = null;
  let _playerId = null;
  let _isHost   = false;
  const _handlers = {};

  function on(event, fn) { _handlers[event] = fn; }
  function _trigger(event, data) { if (_handlers[event]) _handlers[event](data); }

  function connect() {
    if (typeof io === 'undefined') return false;
    _socket = io();
    const events = [
      'connect', 'disconnect', 'hosted', 'joined', 'player_joined',
      'game_started', 'roll_result', 'state_update',
      'player_disconnected', 'player_removed', 'error',
      'space_card', 'space_card_done',
      'rejoined', 'rejoin_failed', 'host_rejoined', 'player_reconnected', 'host_left', 'host_back', 'private_card', 'turn_result', 'card_choice',
    ];
    events.forEach(ev => _socket.on(ev, data => _trigger(ev, data)));
    return true;
  }

  function hostGame(opts)  { _isHost = true; _socket?.emit('host_game', opts); }
  function joinGame(opts)  { _gameId = opts.gameId; _socket?.emit('join_game', opts); }
  function startGame(gameId) { _socket?.emit('start_game', { gameId }); }
  function requestRoll(gameId) { _socket?.emit('roll', { gameId: gameId || _gameId }); }
  // Bypasses the server's random roll — sends a specific value chosen by the host (physical dice play).
  function manualRoll(gameId, roll) { _socket?.emit('manual_roll', { gameId: gameId || _gameId, roll }); }
  function syncState(gameId, stateSlice) { _socket?.emit('sync_state', { gameId, ...stateSlice }); }
  function removePlayer(gameId, playerId) { _socket?.emit('remove_player', { gameId, playerId }); }
  function emitSpaceCard(gameId, cardData) { _socket?.emit('space_card', { gameId, ...cardData }); }
  function emitSpaceCardDone(gameId) { _socket?.emit('space_card_done', { gameId }); }
  function emitTurnResult(gameId, data) { _socket?.emit('turn_result', { gameId, ...data }); }
  function leaveGame(gameId) { _socket?.emit('leave_game', { gameId: gameId || _gameId }); }
  function rejoinGame(gameId, playerId, token) { _socket?.emit('rejoin_game', { gameId, playerId, rejoinToken: token }); }
  function hostRejoin(gameId) { _socket?.emit('host_rejoin', { gameId }); }
  function closeRoom(gameId) { _socket?.emit('close_room', { gameId }); }
  // Host → ONE player's phone (e.g. an action card only the performer may see)
  function sendPrivateCard(gameId, playerId, card) { _socket?.emit('private_card', { gameId, playerId, card }); }
  function sendCardChoice(gameId, promptId, choice) { _socket?.emit('card_choice', { gameId, promptId, choice }); }

  function setGameId(id)   { _gameId = id; }
  function setPlayerId(id) { _playerId = id; }
  function getGameId()     { return _gameId; }
  function getPlayerId()   { return _playerId; }
  function isHostMode()    { return _isHost; }
  function isConnected()   { return !!(_socket?.connected); }

  return {
    on, connect,
    hostGame, joinGame, startGame, requestRoll, manualRoll, syncState,
    removePlayer, emitSpaceCard, emitSpaceCardDone, emitTurnResult, leaveGame,
    rejoinGame, hostRejoin, closeRoom, sendPrivateCard, sendCardChoice,
    setGameId, setPlayerId, getGameId, getPlayerId,
    isHostMode, isConnected,
  };
})();
