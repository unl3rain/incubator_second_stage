const BOARD_SIZE = 8

const DIRECTIONS = {
  red: [1],
  white: [-1],
}

function isInsideBoard(row, col) {
  return row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE
}

function createPiece(player, king = false) {
  return {
    player,
    king,
  }
}

export function createInitialBoard() {
  const board = Array.from({ length: BOARD_SIZE }, () => Array.from({ length: BOARD_SIZE }, () => null))

  for (let row = 0; row < BOARD_SIZE; row += 1) {
    for (let col = 0; col < BOARD_SIZE; col += 1) {
      if ((row + col) % 2 === 0) {
        continue
      }

      if (row < 3) {
        board[row][col] = createPiece('red')
      }

      if (row > 4) {
        board[row][col] = createPiece('white')
      }
    }
  }

  return board
}

function movementDirections(piece) {
  if (piece.king) {
    return [1, -1]
  }

  return DIRECTIONS[piece.player]
}

function captureDirections() {
  return [1, -1]
}

function cloneBoard(board) {
  return board.map((row) => row.map((piece) => (piece ? { ...piece } : null)))
}

function getPieceMoves(board, row, col, forceCaptureOnly = false) {
  const piece = board[row][col]
  if (!piece) {
    return []
  }

  const moves = []

  for (const rowDelta of movementDirections(piece)) {
    for (const colDelta of [-1, 1]) {
      const nextRow = row + rowDelta
      const nextCol = col + colDelta

      if (!isInsideBoard(nextRow, nextCol)) {
        continue
      }

      const nextCell = board[nextRow][nextCol]

      if (!nextCell && !forceCaptureOnly) {
        moves.push({
          from: [row, col],
          to: [nextRow, nextCol],
          capture: null,
        })
        continue
      }

    }
  }

  for (const rowDelta of captureDirections(piece)) {
    for (const colDelta of [-1, 1]) {
      const nextRow = row + rowDelta
      const nextCol = col + colDelta

      if (!isInsideBoard(nextRow, nextCol)) {
        continue
      }

      const nextCell = board[nextRow][nextCol]

      if (!nextCell || nextCell.player === piece.player) {
        continue
      }

      const jumpRow = nextRow + rowDelta
      const jumpCol = nextCol + colDelta

      if (!isInsideBoard(jumpRow, jumpCol)) {
        continue
      }

      if (!board[jumpRow][jumpCol]) {
        moves.push({
          from: [row, col],
          to: [jumpRow, jumpCol],
          capture: [nextRow, nextCol],
        })
      }
    }
  }

  return moves
}

export function getAllMoves(board, player) {
  const allMoves = []

  for (let row = 0; row < BOARD_SIZE; row += 1) {
    for (let col = 0; col < BOARD_SIZE; col += 1) {
      const piece = board[row][col]
      if (!piece || piece.player !== player) {
        continue
      }

      allMoves.push(...getPieceMoves(board, row, col, false))
    }
  }

  const hasCapture = allMoves.some((move) => Boolean(move.capture))

  if (!hasCapture) {
    return allMoves
  }

  return allMoves.filter((move) => Boolean(move.capture))
}

export function getMovesForPiece(board, row, col, player, chainCaptureOnly = false) {
  const piece = board[row][col]
  if (!piece || piece.player !== player) {
    return []
  }

  const allMoves = getAllMoves(board, player)

  if (chainCaptureOnly) {
    return getPieceMoves(board, row, col, true)
  }

  return allMoves.filter((move) => move.from[0] === row && move.from[1] === col)
}

function maybePromote(piece, row) {
  if (piece.king) {
    return piece
  }

  if (piece.player === 'red' && row === BOARD_SIZE - 1) {
    return { ...piece, king: true }
  }

  if (piece.player === 'white' && row === 0) {
    return { ...piece, king: true }
  }

  return piece
}

export function applyMove(board, move) {
  const nextBoard = cloneBoard(board)
  const [fromRow, fromCol] = move.from
  const [toRow, toCol] = move.to
  const movingPiece = nextBoard[fromRow][fromCol]

  nextBoard[fromRow][fromCol] = null

  if (move.capture) {
    const [capturedRow, capturedCol] = move.capture
    nextBoard[capturedRow][capturedCol] = null
  }

  nextBoard[toRow][toCol] = maybePromote(movingPiece, toRow)

  return nextBoard
}

export function detectWinner(board, playerToMove) {
  let redCount = 0
  let whiteCount = 0

  for (let row = 0; row < BOARD_SIZE; row += 1) {
    for (let col = 0; col < BOARD_SIZE; col += 1) {
      const piece = board[row][col]
      if (!piece) {
        continue
      }

      if (piece.player === 'red') {
        redCount += 1
      } else {
        whiteCount += 1
      }
    }
  }

  if (redCount === 0) {
    return 'white'
  }

  if (whiteCount === 0) {
    return 'red'
  }

  const nextMoves = getAllMoves(board, playerToMove)
  if (nextMoves.length === 0) {
    return playerToMove === 'red' ? 'white' : 'red'
  }

  return null
}
