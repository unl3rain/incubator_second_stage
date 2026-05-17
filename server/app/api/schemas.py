from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Player = Literal["white", "red"]
GameMode = Literal["pvp", "vs_ai", "training"]
QuickPlayStatus = Literal["waiting", "matched"]


class PieceOut(BaseModel):
    player: Player
    king: bool


class PlayerInfoOut(BaseModel):
    player_id: str
    nickname: str | None
    city: str | None
    color: Player
    profile_id: str | None = None


class MoveOut(BaseModel):
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    capture: list[int] | None = None


class MoveHistoryItemOut(BaseModel):
    player: Player
    by_ai: bool
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    capture: list[int] | None = None


class MatchPlayerSummaryOut(BaseModel):
    nickname: str | None = None
    city: str | None = None


class MatchSummaryOut(BaseModel):
    id: int
    game_id: str
    mode: GameMode
    winner: Player | None
    ai_elo: int | None = None
    ai_color: Player | None = None
    ranked: bool = False
    season_key: str | None = None
    winner_reason: str | None = None
    time_control_minutes: int | None = None
    total_moves: int
    created_at: datetime
    finished_at: datetime
    players: dict[str, MatchPlayerSummaryOut]


class ReplayStateOut(BaseModel):
    move_index: int
    board: list[list[PieceOut | None]]
    turn: Player
    winner: Player | None
    last_move: MoveHistoryItemOut | None = None


class MatchReplayOut(BaseModel):
    match: MatchSummaryOut
    states: list[ReplayStateOut]


class MatchListResponse(BaseModel):
    matches: list[MatchSummaryOut]


class GameStateOut(BaseModel):
    game_id: str
    board: list[list[PieceOut | None]]
    turn: Player
    winner: Player | None
    forced_piece: list[int] | None
    mode: GameMode = "pvp"
    ai_elo: int | None = None
    ai_color: Player | None = None
    ranked: bool = False
    season_key: str | None = None
    time_control_minutes: int | None = None
    clock_enabled: bool = False
    white_time_ms: int | None = None
    red_time_ms: int | None = None
    active_deadline_at: datetime | None = None
    winner_reason: str | None = None
    players: dict[str, PlayerInfoOut | None]
    legal_moves: list[MoveOut]
    move_history: list[MoveHistoryItemOut] = []


class CreateGameRequest(BaseModel):
    mode: GameMode = "pvp"
    ai_elo: int = 1200
    ai_color: Player = "red"
    ranked: bool = False
    time_control_minutes: int | None = None
    board: list[list[PieceOut | None]] | None = None
    turn: Player | None = None
    forced_piece: list[int] | None = None


class CreateGameResponse(BaseModel):
    game: GameStateOut


class MoveRequest(BaseModel):
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    player_id: str


class UndoMoveRequest(BaseModel):
    player_id: str


class MoveResponse(BaseModel):
    game: GameStateOut
    coach_feedback: "CoachFeedbackOut | None" = None
    coach_feedback_history: list["CoachFeedbackOut"] = Field(default_factory=list)
    ranked_result: dict | None = None


class SuggestedMoveOut(BaseModel):
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    capture: list[int] | None = None


class CoachCandidateOut(BaseModel):
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    capture: list[int] | None = None
    score: int
    confidence: int
    note: str


class CoachFeedbackOut(BaseModel):
    evaluated_player: Player | None = None
    rating: str
    summary: str
    reasons: list[str]
    analysis_mode: str
    search_depth: int
    suggested_move: SuggestedMoveOut | None = None
    top_moves: list[CoachCandidateOut] = []


class JoinGameRequest(BaseModel):
    nickname: str = "Guest"
    city: str | None = None
    preferred_color: Player | None = None
    player_id: str | None = None
    profile_id: str | None = None


class JoinGameResponse(BaseModel):
    game: GameStateOut
    player_id: str
    color: Player | None
    nickname: str | None
    city: str | None
    profile_id: str


class PlayerProfileResponse(BaseModel):
    profile_id: str
    nickname: str
    city: str | None
    games: int
    wins: int
    losses: int
    pvp_games: int
    ai_games: int
    elo_rating: int
    ranked_games: int
    ranked_wins: int
    ranked_losses: int
    ranked_placement_remaining: int
    last_ranked_at: datetime | None = None
    season_key: str
    pro_active: bool = False
    pro_plan: str | None = None
    pro_expires_at: datetime | None = None
    linked_provider: str | None = None
    linked_provider_user_id: str | None = None
    linked_provider_display_name: str | None = None
    owned_board_skins: list[str] = Field(default_factory=list)
    owned_piece_skins: list[str] = Field(default_factory=list)
    equipped_board_skin: str = "classic"
    equipped_piece_skin: str = "marble"
    win_rate: float
    created_at: datetime
    updated_at: datetime


class RankedPlayerOut(BaseModel):
    profile_id: str
    nickname: str
    city: str | None = None
    elo_rating: int
    ranked_games: int
    ranked_wins: int
    ranked_losses: int
    ranked_placement_remaining: int
    season_key: str
    inactivity_days: int = 0
    days_until_hidden: int = 30
    activity_status: Literal["active", "inactive-soon"] = "active"


class RankedLeaderboardResponse(BaseModel):
    season_key: str
    players: list[RankedPlayerOut]


class QuickPlayEnqueueRequest(BaseModel):
    nickname: str = "Guest"
    city: str | None = None
    preferred_color: Player | None = None
    profile_id: str | None = None
    ranked: bool = True
    time_control_minutes: int = 5


class QuickPlayStatusResponse(BaseModel):
    status: QuickPlayStatus
    ticket_id: str
    queue_size: int
    game: GameStateOut | None = None
    player_id: str | None = None
    color: Player | None = None
    nickname: str | None = None
    city: str | None = None
    profile_id: str | None = None
    opponent_nickname: str | None = None


class ProfileMatchSummaryOut(MatchSummaryOut):
    role_color: Player
    did_win: bool


class ProfileMatchListResponse(BaseModel):
    matches: list[ProfileMatchSummaryOut]


class DailyPuzzleOut(BaseModel):
    puzzle_date: str
    title: str
    hint: str
    difficulty: str
    source: str
    source_url: str | None = None
    attribution: str | None = None
    board: list[list[PieceOut | None]]
    turn: Player
    solved_today: bool
    attempts_today: int
    streak: int


class DailyPuzzleSubmitRequest(BaseModel):
    profile_id: str
    puzzle_date: str
    from_pos: list[int] = Field(alias="from")
    to: list[int]


class DailyPuzzleSubmitResponse(BaseModel):
    correct: bool
    solved_today: bool
    streak: int
    message: str


class PuzzleBankImportEntry(BaseModel):
    code: str | None = None
    title: str
    hint: str
    difficulty: str = "easy"
    turn: Player
    board: list[list[PieceOut | None]]
    solution: SuggestedMoveOut


class PuzzleBankImportRequest(BaseModel):
    source: str
    source_url: str | None = None
    attribution: str | None = None
    dry_run: bool = False
    puzzles: list[PuzzleBankImportEntry]


class PuzzleBankImportResponse(BaseModel):
    total: int
    inserted: int
    updated: int
    skipped: int
    errors: list[str]


class LeaderboardCityOut(BaseModel):
    city: str
    wins: int
    games: int


class LeaderboardResponse(BaseModel):
    cities: list[LeaderboardCityOut]


class EngineStatusResponse(BaseModel):
    provider: str
    available: bool
    import_ok: bool
    reason: str
    configured_depth: int
    configured_time_limit: float


class BillingCheckoutRequest(BaseModel):
    profile_id: str
    plan: Literal["pro_monthly", "pro_yearly"] = "pro_monthly"


class BillingCheckoutResponse(BaseModel):
    checkout_url: str
    mode: Literal["stripe", "mock"]


class BillingWebhookResponse(BaseModel):
    ok: bool


class CosmeticsResponse(BaseModel):
    profile_id: str
    pro_active: bool
    pro_plan: str | None = None
    pro_expires_at: datetime | None = None
    owned_board_skins: list[str]
    owned_piece_skins: list[str]
    equipped_board_skin: str
    equipped_piece_skin: str


class EquipSkinRequest(BaseModel):
    kind: Literal["board", "piece"]
    skin_id: str


class AuthLoginRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None


class AuthLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    session_id: str
    expires_in_seconds: int
    profile_id: str
    username: str
    email: str | None = None
    email_verified: bool = False


class AuthSocialLoginRequest(BaseModel):
    provider: Literal["google", "github", "apple", "discord"]
    provider_user_id: str
    email: str | None = None
    username: str | None = None


class AuthGoogleStartResponse(BaseModel):
    auth_url: str


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


class AuthRegisterResponse(BaseModel):
    profile_id: str
    username: str
    email: str
    email_verified: bool


class AuthVerifyEmailRequest(BaseModel):
    email: str
    code: str


class AuthSimpleResponse(BaseModel):
    ok: bool
    message: str


class AuthForgotPasswordRequest(BaseModel):
    email: str


class AuthForgotPasswordResponse(BaseModel):
    ok: bool
    message: str


class AuthResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    session_id: str
    expires_in_seconds: int


class AuthSessionOut(BaseModel):
    session_id: str
    device_label: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_seen_at: datetime
    refresh_expires_at: datetime


class AuthSessionsResponse(BaseModel):
    sessions: list[AuthSessionOut]


class AuthRevokeAllRequest(BaseModel):
    keep_current: bool = False


class AuthRevokeSessionRequest(BaseModel):
    session_id: str


class AccuracyMoveOut(BaseModel):
    move_number: int
    from_pos: list[int] = Field(alias="from")
    to: list[int]
    rating: str  # "blunder", "mistake", "inaccuracy", "ok", "good", "best"
    player: Literal["white", "red"]
    score_delta: float = 0.0
    best_move: SuggestedMoveOut | None = None
    summary: str | None = None


class AccuracyScoreResponse(BaseModel):
    game_id: str
    blunders: int
    mistakes: int
    inaccuracies: int
    oks: int
    goods: int
    bests: int
    accuracy_percent: float  # (bests + goods) / total_moves * 100
    moves: list[AccuracyMoveOut]


class PuzzleOut(BaseModel):
    puzzle_id: str
    difficulty: Literal["easy", "medium", "hard"]
    title: str
    hint: str
    board: list[list[PieceOut | None]]
    player_to_move: Literal["white", "red"]
    source: str | None = None


class PuzzleRushStartResponse(BaseModel):
    session_id: str
    puzzles: list[PuzzleOut]
    time_limit_seconds: int
    difficulty: str


class PuzzleRushSubmitRequest(BaseModel):
    session_id: str
    puzzle_id: str
    moves: list[dict]  # User's attempted solution


class PuzzleRushResultResponse(BaseModel):
    correct: bool
    time_taken_seconds: float
    score_earned: int
    total_score: int
    puzzles_solved: int
    time_remaining: int
    next_puzzle: PuzzleOut | None


class PuzzleRushFinishResponse(BaseModel):
    session_id: str
    final_score: int
    puzzles_solved: int
    duration_seconds: float
    status: str


class AnalyticsEventRequest(BaseModel):
    event_name: str
    profile_id: str | None = None
    game_id: str | None = None
    source: str = "web"
    properties: dict = Field(default_factory=dict)


class AnalyticsEventResponse(BaseModel):
    ok: bool
    event_id: int


class AnalyticsDailySummaryOut(BaseModel):
    date: str
    events: int
    unique_profiles: int


class AnalyticsSummaryResponse(BaseModel):
    period_days: int
    total_events: int
    unique_profiles: int
    event_counts: dict[str, int]
    funnel: dict[str, int]
    daily: list[AnalyticsDailySummaryOut]


class FriendOut(BaseModel):
    profile_id: str
    nickname: str
    city: str | None = None
    status: str
    friendship_id: str
    created_at: datetime


class FriendRequestOut(BaseModel):
    friendship_id: str
    requester_profile_id: str
    requester_nickname: str
    requester_city: str | None = None
    created_at: datetime


class FriendsListResponse(BaseModel):
    friends: list[FriendOut]
    pending_requests: list[FriendRequestOut]


class FriendRequestCreate(BaseModel):
    target_profile_id: str


class FriendRequestAction(BaseModel):
    friendship_id: str


class ChatMessageOut(BaseModel):
    message_id: str
    game_id: str
    sender_profile_id: str
    sender_nickname: str
    text: str
    message_type: str
    created_at: datetime


class ChatMessagesResponse(BaseModel):
    messages: list[ChatMessageOut]


class ChatCreateRequest(BaseModel):
    text: str
    message_type: Literal["text", "emoji"] = "text"


class ChatReportRequest(BaseModel):
    reason: str = "abusive"


class ChatMuteRequest(BaseModel):
    muted_profile_id: str
    muted: bool = True


class ChatMuteListResponse(BaseModel):
    muted_profile_ids: list[str]
