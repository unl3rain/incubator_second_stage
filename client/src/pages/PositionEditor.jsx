import React, { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';
const initialBoard = Array(8).fill(null).map(() => Array(8).fill(null));

function boardSquareClass(row, col) {
  const isLight = (row + col) % 2 === 0;
  return isLight ? 'bg-emerald-100' : 'bg-emerald-800';
}

function pieceClass(piece) {
  if (!piece) return '';
  return piece.player === 'white'
    ? 'bg-gradient-to-br from-slate-50 via-slate-200 to-slate-500 text-slate-900'
    : 'bg-gradient-to-br from-rose-300 via-rose-600 to-rose-950 text-white';
}

export default function PositionEditor({ auth }) {
  const [board, setBoard] = useState(initialBoard);
  const [selected, setSelected] = useState(null);
  const [currentPlayer, setCurrentPlayer] = useState('white');
  const [isKing, setIsKing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [trainingMode, setTrainingMode] = useState('vs_ai');

  const handleSquareClick = (row, col) => {
    setSelected([row, col]);
  };

  const handlePlacePiece = () => {
    if (!selected) {
      setMessage('Select a square first');
      return;
    }
    const [row, col] = selected;
    setBoard(prev => {
      const next = prev.map(r => [...r]);
      next[row][col] = { player: currentPlayer, king: isKing };
      return next;
    });
    setMessage(`Placed ${isKing ? 'king' : 'piece'} at selected square`);
  };

  const handleRemovePiece = () => {
    if (!selected) {
      setMessage('Select a square first');
      return;
    }
    const [row, col] = selected;
    setBoard(prev => {
      const next = prev.map(r => [...r]);
      next[row][col] = null;
      return next;
    });
    setMessage('Removed piece from selected square');
  };

  const handleClearBoard = () => {
    setBoard(initialBoard);
    setSelected(null);
    setMessage('Board cleared');
  };

  const handleStartTraining = async () => {
    setLoading(true);
    setMessage('');
    try {
      const payload = trainingMode === 'self' 
        ? { mode: 'training', board: board, turn: 'white' }
        : { mode: 'vs_ai', board: board, turn: 'white', ai_elo: 1200, ranked: false };
      
      const createResponse = await fetch(`${API_BASE}/games`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      const createData = await createResponse.json().catch((e) => {
        console.error('Failed to parse response:', e);
        return {};
      });
      
      if (!createResponse.ok) {
        throw new Error(createData.detail || `HTTP ${createResponse.status}`);
      }
      
      if (!createData.game || !createData.game.game_id) {
        throw new Error('No game_id in response');
      }
      
      localStorage.setItem('custom_training_game_id', createData.game.game_id);
      window.location.href = '/training';
    } catch (err) {
      console.error('Error starting training:', err);
      setMessage(`Failed to start training: ${err.message}`);
      setLoading(false);
    }
  };
  
  const handleTestApi = async () => {
    try {
      const response = await fetch(`${API_BASE}/engine/status`);
      const data = await response.json();
      setMessage(`✓ API is working: ${data.provider} (${data.reason})`);
    } catch (err) {
      setMessage(`✗ API test failed: ${err.message}`);
    }
  };

  const isPro = auth?.subscription === 'pro';
  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-gradient-to-br from-teal-100 via-emerald-50 to-cyan-50 p-6 shadow-sm sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Training</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">Position Editor</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">Create a custom board position and start a training session. Select squares, place or remove pieces, then launch into AI sparring.</p>
      </section>

      {message ? (
        <div className="rounded-2xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
          {message}
        </div>
      ) : null}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6 flex flex-wrap gap-3 items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700">Board setup</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900">Editor</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleTestApi}
              type="button"
              className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600 transition hover:bg-slate-100"
            >
              Test API
            </button>
            <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
              <span className="font-semibold text-slate-700">Piece:</span>
              <select
                value={currentPlayer}
                onChange={e => setCurrentPlayer(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-sm font-semibold text-slate-700"
              >
                <option value="white">White</option>
                <option value="red">Red</option>
              </select>
            </label>
            <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
              <input type="checkbox" checked={isKing} onChange={e => setIsKing(e.target.checked)} className="w-4 h-4" />
              <span>King</span>
            </label>
            <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
              <span className="font-semibold text-slate-700">Mode:</span>
              <select
                value={trainingMode}
                onChange={e => setTrainingMode(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-sm font-semibold text-slate-700"
              >
                <option value="vs_ai">vs AI</option>
                <option value="self">Self-Analysis</option>
              </select>
            </label>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-4 mb-4">
          <div className="grid grid-cols-8 gap-0 w-fit">
            {board.map((row, rowIndex) =>
              row.map((piece, colIndex) => {
                const isSelected = selected && selected[0] === rowIndex && selected[1] === colIndex;
                return (
                  <button
                    key={`${rowIndex}-${colIndex}`}
                    type="button"
                    onClick={() => handleSquareClick(rowIndex, colIndex)}
                    className={`relative aspect-square w-10 h-10 flex items-center justify-center transition ${
                      isSelected ? 'ring-4 ring-amber-400' : ''
                    } ${boardSquareClass(rowIndex, colIndex)}`}
                    aria-label={`Square ${rowIndex + 1}, ${colIndex + 1}`}
                  >
                    {piece ? (
                      <span className={`flex w-8 h-8 items-center justify-center rounded-full border border-white/50 shadow-md font-bold text-sm ${pieceClass(piece)}`}>
                        {piece.king ? 'K' : ''}
                      </span>
                    ) : null}
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={handlePlacePiece}
            disabled={loading}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-60"
          >
            Place piece
          </button>
          <button
            onClick={handleRemovePiece}
            disabled={loading}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:opacity-60"
          >
            Remove piece
          </button>
          <button
            onClick={handleClearBoard}
            disabled={loading}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
          >
            Clear board
          </button>
          <button
            onClick={handleStartTraining}
            disabled={loading || !isPro}
            className="ml-auto rounded-lg bg-teal-700 px-6 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-teal-800 disabled:opacity-60"
            title={!isPro ? 'Upgrade to Pro to unlock training' : ''}
          >
            {loading ? 'Starting...' : `Start ${trainingMode === 'self' ? 'self-analysis' : 'AI training'}`}
          </button>
          {!isPro && (
            <button
              type="button"
              className="ml-2 rounded-lg border border-amber-400 bg-amber-100 px-4 py-2 text-sm font-semibold text-amber-900 transition hover:bg-amber-200"
              onClick={auth?.openDemoPayment}
            >
              Go Pro to unlock
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
