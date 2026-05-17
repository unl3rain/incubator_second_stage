import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from app.models.auth_user import AuthUser

from app.api.schemas import (
    CoachFeedbackOut,
    CreateGameRequest,
    CreateGameResponse,
    DailyPuzzleOut,
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingWebhookResponse,
    CosmeticsResponse,
    EquipSkinRequest,
    PuzzleBankImportRequest,
    PuzzleBankImportResponse,
    DailyPuzzleSubmitRequest,
    DailyPuzzleSubmitResponse,
    EngineStatusResponse,
    GameStateOut,
    LeaderboardResponse,
    JoinGameRequest,
    JoinGameResponse,
    MatchListResponse,
    MatchReplayOut,
    MoveRequest,
    MoveResponse,
    UndoMoveRequest,
    QuickPlayEnqueueRequest,
    QuickPlayStatusResponse,
    RankedLeaderboardResponse,
    ProfileMatchListResponse,
    PlayerProfileResponse,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthSocialLoginRequest,
    AuthGoogleStartResponse,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthVerifyEmailRequest,
    AuthSimpleResponse,
    AuthForgotPasswordRequest,
    AuthForgotPasswordResponse,
    AuthResetPasswordRequest,
    AuthRefreshRequest,
    AuthRefreshResponse,
    AuthSessionsResponse,
    AuthRevokeAllRequest,
    AuthRevokeSessionRequest,
    AccuracyScoreResponse,
    PuzzleRushStartResponse,
    PuzzleRushSubmitRequest,
    PuzzleRushResultResponse,
    PuzzleRushFinishResponse,
    AnalyticsEventRequest,
    AnalyticsEventResponse,
    AnalyticsSummaryResponse,
    FriendsListResponse,
    FriendRequestCreate,
    FriendRequestAction,
    ChatMessagesResponse,
    ChatCreateRequest,
    ChatMessageOut,
    ChatReportRequest,
    ChatMuteRequest,
    ChatMuteListResponse,
)
from app.services.analytics import get_analytics_summary, track_event
from app.services.retention import get_active_missions, get_achievements, issue_daily_missions, issue_weekly_missions, update_mission_progress, get_pending_notifications, mark_notification_as_read
from app.services.ai_opponent import choose_ai_move
from app.services.advanced_engine import get_engine_status
from app.services.coach import analyze_move_quality
from app.services.auth import (
    authenticate_user,
    authenticate_social_user,
    create_or_get_user,
    create_password_reset,
    extract_bearer_token,
    issue_session_tokens,
    is_valid_email,
    list_active_sessions,
    register_user,
    revoke_all_sessions,
    revoke_session,
    reset_password,
    revoke_token,
    rotate_refresh_token,
    verify_token,
    verify_email_code,
)
from app.services.accuracy import calculate_accuracy_score
from app.services.billing import create_checkout_session, handle_webhook
from app.services.daily_puzzle import get_daily_puzzle, submit_daily_puzzle
from app.services.entitlements import equip_skin, get_profile_entitlements
from app.services.leaderboard import get_top_cities, record_finished_game
from app.services.match_archive import get_match_replay, get_recent_matches, save_completed_game
from app.services.oauth_google import (
    build_google_auth_url,
    consume_google_oauth_state,
    exchange_google_code_for_profile,
    issue_google_oauth_state,
)
from app.services.oauth_github import (
    build_github_auth_url,
    consume_github_oauth_state,
    exchange_github_code_for_profile,
    issue_github_oauth_state,
)
from app.services.coach_gemini import get_pro_coach_analysis
from app.services.puzzle_bank_import import import_puzzles
from app.services.puzzle_rush import start_puzzle_rush, submit_puzzle_solution, finish_puzzle_rush, get_session
from app.services.profile_stats import (
    get_ranked_leaderboard,
    get_or_create_profile,
    get_profile,
    get_profile_matches,
    link_profile_to_completed_match,
    record_ranked_elo_result,
    record_profile_result,
)
from app.services.quick_play import quick_play_queue
from app.services.game_store import store
from app.services.realtime import realtime
from app.services.social import (
    accept_friend_request,
    create_chat_message,
    get_friends,
    get_pending_friend_requests,
    list_chat_messages,
    list_mutes,
    remove_friend,
    report_chat_message,
    send_friend_request,
    set_mute,
)
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["api"])


def _require_profile_id_from_auth(request: Request) -> str:
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    claims = verify_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    profile_id = claims.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=401, detail="Token missing profile_id")
    return profile_id


def _advance_ai_turns(game_id: str) -> None:
    while store.is_ai_turn(game_id):
        current = store.get_game(game_id)
        if current is None or current.ai_color is None:
            break

        ai_moves = store.current_candidate_moves(game_id)
        if not ai_moves:
            break

        ai_move = choose_ai_move(current.board, current.turn, ai_moves, current.ai_elo or 1200)
        store.apply_system_move(game_id, ai_move["from_"], ai_move["to"], current.ai_color)


def _finalize_finished_game(summary: dict, mover_player_id: str | None = None, game: object | None = None) -> dict | None:
    if summary is None:
        return None

    elo_summary = None
    if summary.get("ranked") and summary.get("winner") in {"white", "red"}:
        white_profile_id = summary["players"].get("white", {}).get("profile_id")
        red_profile_id = summary["players"].get("red", {}).get("profile_id")
        if white_profile_id and red_profile_id:
            elo_summary = record_ranked_elo_result(
                white_profile_id=white_profile_id,
                red_profile_id=red_profile_id,
                winner=summary["winner"],
            )
            if elo_summary is not None:
                summary["season_key"] = elo_summary.get("season_key")

    record_finished_game(summary["winner_city"], summary["loser_city"])
    for color in ("white", "red"):
        player_profile_id = summary["players"].get(color, {}).get("profile_id")
        if not player_profile_id:
            continue

        record_profile_result(
            player_profile_id,
            did_win=summary["winner"] == color,
            mode=summary["mode"],
            ranked=bool(summary.get("ranked")),
        )

    save_completed_game(summary)
    link_profile_to_completed_match(summary)

    if elo_summary is None or mover_player_id is None or game is None:
        return None

    mover_profile_id = getattr(game, "profiles", {}).get(mover_player_id, {}).get("profile_id")
    if not mover_profile_id:
        return None

    white_profile_id = summary["players"].get("white", {}).get("profile_id")
    if mover_profile_id == white_profile_id:
        before_rating = elo_summary["white_before"]
        after_rating = elo_summary["white_after"]
    else:
        before_rating = elo_summary["red_before"]
        after_rating = elo_summary["red_after"]

    return {
        "before": before_rating,
        "after": after_rating,
        "delta": after_rating - before_rating,
        "season_key": elo_summary.get("season_key"),
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "checkers-api"}


@router.get("/engine/status", response_model=EngineStatusResponse)
def engine_status() -> dict:
    return get_engine_status()


@router.get("/puzzles/daily", response_model=DailyPuzzleOut)
def daily_puzzle(profile_id: str | None = None) -> dict:
    return get_daily_puzzle(profile_id)


@router.post("/puzzles/daily/submit", response_model=DailyPuzzleSubmitResponse)
def submit_puzzle(payload: DailyPuzzleSubmitRequest) -> dict:
    if len(payload.from_pos) != 2 or len(payload.to) != 2:
        raise HTTPException(status_code=422, detail="from and to must be [row, col]")

    return submit_daily_puzzle(payload.profile_id, payload.puzzle_date, payload.from_pos, payload.to)


@router.post("/puzzles/import", response_model=PuzzleBankImportResponse)
def import_puzzle_bank(payload: PuzzleBankImportRequest) -> dict:
    if not payload.puzzles:
        raise HTTPException(status_code=422, detail="puzzles array cannot be empty")

    return import_puzzles(payload.model_dump(by_alias=True))


@router.post("/games", response_model=CreateGameResponse)
def create_game(payload: CreateGameRequest | None = None) -> dict:
    if payload is None:
        game = store.create_game()
    else:
        game = store.create_game(
            mode=payload.mode,
            ai_elo=payload.ai_elo,
            ai_color=payload.ai_color,
            ranked=payload.ranked,
            time_control_minutes=payload.time_control_minutes,
            board=payload.board,
            turn=payload.turn or "white",
            forced_piece=tuple(payload.forced_piece) if payload.forced_piece and len(payload.forced_piece) == 2 else None,
        )

    _advance_ai_turns(game.game_id)
    return {"game": store.serialize_game(game)}


@router.get("/games/{game_id}", response_model=GameStateOut)
def get_game(game_id: str) -> dict:
    game = store.get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return store.serialize_game(game)


@router.post("/games/{game_id}/join", response_model=JoinGameResponse)
def join_game(game_id: str, payload: JoinGameRequest) -> dict:
    persistent_profile = get_or_create_profile(payload.profile_id, payload.nickname, payload.city)

    try:
        game, player = store.join_game(
            game_id=game_id,
            nickname=persistent_profile["nickname"],
            city=persistent_profile["city"],
            preferred_color=payload.preferred_color,
            player_id=payload.player_id,
            profile_id=persistent_profile["profile_id"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _advance_ai_turns(game_id)

    return {
        "game": store.serialize_game(game),
        **player,
    }


@router.post("/games/{game_id}/moves", response_model=MoveResponse)
async def make_move(game_id: str, payload: MoveRequest) -> dict:
    if len(payload.from_pos) != 2 or len(payload.to) != 2:
        raise HTTPException(status_code=422, detail="from and to must be [row, col]")

    from_pos = (payload.from_pos[0], payload.from_pos[1])
    to_pos = (payload.to[0], payload.to[1])

    try:
        game, selected_move, candidate_moves, board_before = store.apply_player_move_detailed(
            game_id,
            from_pos,
            to_pos,
            payload.player_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    piece_before = board_before[from_pos[0]][from_pos[1]]
    player_color = piece_before["player"] if piece_before is not None else "white"
    
    # Coach feedback only in training mode or after game is finished
    # Disabled during active PvP/ranked for fairness
    coach_feedback = None
    coach_feedback_history = []
    if game.mode in {"training", "vs_ai"} or game.winner is not None:
        coach_feedback = analyze_move_quality(board_before, player_color, selected_move, candidate_moves)
        if coach_feedback:
            coach_feedback["evaluated_player"] = player_color
            coach_feedback_history.append(coach_feedback)
        
        # Enhance coach feedback with Gemini for Pro users
        if coach_feedback:
            mover_profile_id = game.profiles.get(payload.player_id, {}).get("profile_id")
            profile = get_profile(mover_profile_id) if mover_profile_id else None
            if profile and profile.get("pro_active"):
                pro_analysis = get_pro_coach_analysis(
                    board_state=str(board_before),
                    move_history=game.move_history[-5:] if hasattr(game, 'move_history') else [],
                    current_move={"from": from_pos, "to": to_pos},
                    coach_feedback=coach_feedback,
                    player_nickname=profile.get("nickname", "Player"),
                )
                if pro_analysis:
                    coach_feedback["pro_depth"] = pro_analysis

    while store.is_ai_turn(game_id):
        current = store.get_game(game_id)
        if current is None or current.ai_color is None:
            break

        ai_moves = store.current_candidate_moves(game_id)
        if not ai_moves:
            break

        ai_move = choose_ai_move(current.board, current.turn, ai_moves, current.ai_elo or 1200)
        ai_feedback = analyze_move_quality(current.board, current.turn, ai_move, ai_moves)
        ai_feedback["evaluated_player"] = current.turn
        coach_feedback_history.append(ai_feedback)
        store.apply_system_move(game_id, ai_move["from_"], ai_move["to"], current.ai_color)

    ranked_result = _finalize_finished_game(
        store.consume_finished_summary(game_id),
        mover_player_id=payload.player_id,
        game=game,
    )

    await realtime.broadcast(
        game_id,
        {
            "type": "game_updated",
            "game": store.serialize_game(game),
        },
    )

    return {
        "game": store.serialize_game(game),
        "coach_feedback": coach_feedback,
        "coach_feedback_history": coach_feedback_history,
        "ranked_result": ranked_result,
    }


@router.post("/games/{game_id}/undo", response_model=MoveResponse)
def undo_training_move(game_id: str, payload: UndoMoveRequest) -> dict:
    try:
        game = store.undo_last_training_turn(game_id, payload.player_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"game": store.serialize_game(game), "coach_feedback": None, "ranked_result": None}


@router.post("/billing/checkout", response_model=BillingCheckoutResponse)
def billing_checkout(payload: BillingCheckoutRequest) -> dict:
    return create_checkout_session(payload.profile_id, payload.plan)


@router.post("/billing/webhook", response_model=BillingWebhookResponse)
async def billing_webhook(request: Request) -> dict:
    signature = request.headers.get("stripe-signature")
    body = await request.body()
    return handle_webhook(body, signature)


@router.get("/matches/recent", response_model=MatchListResponse)
def recent_matches(limit: int = 10) -> dict:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50")

    return {"matches": get_recent_matches(limit)}


@router.get("/matches/{match_id}", response_model=MatchReplayOut)
def match_replay(match_id: int) -> dict:
    replay = get_match_replay(match_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Match not found")

    return replay


@router.get("/leaderboard/cities", response_model=LeaderboardResponse)
def city_leaderboard(limit: int = 10) -> dict:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")

    return {"cities": get_top_cities(limit)}


@router.get("/leaderboard/ranked", response_model=RankedLeaderboardResponse)
def ranked_leaderboard(limit: int = 20) -> dict:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")

    return get_ranked_leaderboard(limit)


@router.post("/quick-play/enqueue", response_model=QuickPlayStatusResponse)
def quick_play_enqueue(payload: QuickPlayEnqueueRequest) -> dict:
    if payload.time_control_minutes not in {1, 3, 5, 10}:
        raise HTTPException(status_code=422, detail="time_control_minutes must be one of 1, 3, 5, 10")

    persistent_profile = get_or_create_profile(payload.profile_id, payload.nickname, payload.city)
    status = quick_play_queue.enqueue(
        nickname=persistent_profile["nickname"],
        city=persistent_profile["city"],
        preferred_color=payload.preferred_color,
        profile_id=persistent_profile["profile_id"],
        ranked=payload.ranked,
        time_control_minutes=payload.time_control_minutes,
    )
    status["profile_id"] = persistent_profile["profile_id"]
    status["nickname"] = persistent_profile["nickname"]
    status["city"] = persistent_profile["city"]
    return status


@router.get("/quick-play/status/{ticket_id}", response_model=QuickPlayStatusResponse)
def quick_play_status(ticket_id: str) -> dict:
    status = quick_play_queue.get_status(ticket_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return status


@router.delete("/quick-play/status/{ticket_id}")
def quick_play_cancel(ticket_id: str) -> dict:
    canceled = quick_play_queue.cancel(ticket_id)
    if not canceled:
        raise HTTPException(status_code=400, detail="Ticket is not in waiting state")

    return {"ok": True}


@router.get("/profiles/{profile_id}", response_model=PlayerProfileResponse)
def profile_stats(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


@router.get("/profiles/{profile_id}/matches", response_model=ProfileMatchListResponse)
def profile_matches(profile_id: str, limit: int = 10) -> dict:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50")

    return {"matches": get_profile_matches(profile_id, limit)}


@router.get("/profiles/{profile_id}/cosmetics", response_model=CosmeticsResponse)
def profile_cosmetics(profile_id: str) -> dict:
    data = get_profile_entitlements(profile_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return data


@router.post("/profiles/{profile_id}/cosmetics/equip", response_model=CosmeticsResponse)
def equip_profile_skin(profile_id: str, payload: EquipSkinRequest) -> dict:
    try:
        result = equip_skin(profile_id, payload.kind, payload.skin_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    data = get_profile_entitlements(profile_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return data


@router.websocket("/ws/games/{game_id}")
async def game_room_socket(websocket: WebSocket, game_id: str) -> None:
    game = store.get_game(game_id)
    if game is None:
        await websocket.close(code=4404, reason="Game not found")
        return

    await realtime.connect(game_id, websocket)

    await realtime.broadcast(
        game_id,
        {
            "type": "presence",
            "event": "joined",
            "game": store.serialize_game(game),
        },
    )

    player_id = websocket.query_params.get("player_id")
    if player_id:
        store.mark_player_connected(game_id, player_id)

        await websocket.send_json(
            jsonable_encoder(
                {
                    "type": "game_snapshot",
                    "game": store.serialize_game(game),
                }
            )
        )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "chat_send":
                profile_id = (message.get("profile_id") or "").strip()
                text = message.get("text") or ""
                message_type = message.get("message_type") or "text"

                if not profile_id:
                    await websocket.send_json({"type": "chat_error", "detail": "profile_id is required"})
                    continue

                try:
                    chat_item = create_chat_message(game_id, profile_id, text, message_type=message_type)
                except ValueError as exc:
                    await websocket.send_json({"type": "chat_error", "detail": str(exc)})
                    continue

                await realtime.broadcast(game_id, {"type": "chat_message", "message": chat_item})
    except WebSocketDisconnect:
        realtime.disconnect(game_id, websocket)
        if player_id:
            store.mark_player_disconnected(game_id, player_id)

            async def _enforce_disconnect_grace() -> None:
                await asyncio.sleep(20)
                forfeited = store.forfeit_if_still_disconnected(game_id, player_id, grace_seconds=20)
                if forfeited:
                    _finalize_finished_game(store.consume_finished_summary(game_id))
                    current_game = store.get_game(game_id)
                    if current_game is not None:
                        await realtime.broadcast(
                            game_id,
                            {
                                "type": "game_updated",
                                "game": store.serialize_game(current_game),
                            },
                        )

            asyncio.create_task(_enforce_disconnect_grace())

        game = store.get_game(game_id)
        if game is not None:
            await realtime.broadcast(
                game_id,
                {
                    "type": "presence",
                    "event": "left",
                    "game": store.serialize_game(game),
                },
            )


@router.post("/auth/register", response_model=AuthRegisterResponse)
def auth_register(payload: AuthRegisterRequest) -> dict:
    try:
        user = register_user(payload.email, payload.password, payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "profile_id": user["profile_id"],
        "username": user["username"] or "Guest",
        "email": user["email"],
        "email_verified": bool(user.get("email_verified")),
    }


@router.post("/auth/verify-email", response_model=AuthSimpleResponse)
def auth_verify_email(payload: AuthVerifyEmailRequest) -> dict:
    if not verify_email_code(payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    return {"ok": True, "message": "Email verified successfully"}


@router.post("/auth/login", response_model=AuthLoginResponse)
def login(payload: AuthLoginRequest, request: Request) -> dict:
    """JWT login with refresh session support."""
    username = (payload.username or "").strip() or None
    email = (payload.email or "").strip() or None

    if not username and not email:
        raise HTTPException(status_code=422, detail="Provide either username or email")

    if email and not is_valid_email(email):
        raise HTTPException(status_code=422, detail="Invalid email format")

    if payload.password:
        identifier = email or username
        if not identifier:
            raise HTTPException(status_code=422, detail="Email or username required for password login")
        user = authenticate_user(identifier, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        user = create_or_get_user(username=username, email=email)

    tokens = issue_session_tokens(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "session_id": tokens["session_id"],
        "expires_in_seconds": tokens["expires_in_seconds"],
        "profile_id": user["profile_id"],
        "username": user.get("username") or "Guest",
        "email": user.get("email"),
        "email_verified": bool(user.get("email_verified")),
    }


@router.post("/auth/social-login", response_model=AuthLoginResponse)
def social_login(payload: AuthSocialLoginRequest, request: Request) -> dict:
    try:
        user = authenticate_social_user(
            provider=payload.provider,
            provider_user_id=payload.provider_user_id,
            email=payload.email,
            username=payload.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tokens = issue_session_tokens(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "session_id": tokens["session_id"],
        "expires_in_seconds": tokens["expires_in_seconds"],
        "profile_id": user["profile_id"],
        "username": user.get("username") or "Guest",
        "email": user.get("email"),
        "email_verified": bool(user.get("email_verified")),
    }


@router.get("/auth/google/start", response_model=AuthGoogleStartResponse)
def auth_google_start(oauth_session: str) -> dict:
    try:
        state, nonce = issue_google_oauth_state(oauth_session)
        auth_url = build_google_auth_url(state, nonce)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"auth_url": auth_url}


@router.get("/auth/google/callback", response_class=HTMLResponse)
def auth_google_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> HTMLResponse:
    target_origin = settings.frontend_origin

    def popup_html(message_type: str, payload: dict) -> HTMLResponse:
        safe_payload = json.dumps(payload)
        safe_type = json.dumps(message_type)
        safe_origin = json.dumps(target_origin)
        html = f"""
<!doctype html>
<html>
  <body style=\"font-family: Arial, sans-serif; padding: 16px;\">
    <p>Completing sign-in...</p>
    <script>
      (function() {{
        const message = {{ type: {safe_type}, payload: {safe_payload} }};
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(message, {safe_origin});
          window.close();
        }} else {{
          document.body.innerText = 'Sign-in complete. You can close this window.';
        }}
      }})();
    </script>
  </body>
</html>
"""
        return HTMLResponse(content=html)

    if error:
        return popup_html("checkers_google_auth_error", {"message": f"Google auth failed: {error}"})

    state_payload = consume_google_oauth_state(state or "") if state else None
    if state_payload is None:
        return popup_html("checkers_google_auth_error", {"message": "Invalid or expired OAuth state."})

    if not code:
        return popup_html("checkers_google_auth_error", {"message": "Missing authorization code."})

    try:
        profile = exchange_google_code_for_profile(code, expected_nonce=state_payload.get("nonce", ""))
        user = authenticate_social_user(
            provider="google",
            provider_user_id=profile.get("sub", ""),
            email=profile.get("email"),
            username=profile.get("name") or profile.get("given_name"),
        )
        tokens = issue_session_tokens(user)
    except Exception as exc:
        return popup_html("checkers_google_auth_error", {"message": f"Google login failed: {str(exc)}"})

    return popup_html(
        "checkers_google_auth_success",
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "session_id": tokens["session_id"],
            "expires_in_seconds": tokens["expires_in_seconds"],
            "profile_id": user["profile_id"],
            "username": user.get("username") or "Guest",
            "email": user.get("email"),
            "email_verified": bool(user.get("email_verified")),
            "oauth_session": state_payload.get("oauth_session"),
        },
    )


@router.get("/auth/github/start", response_model=AuthGoogleStartResponse)
def auth_github_start(oauth_session: str) -> dict:
    try:
        state, nonce = issue_github_oauth_state(oauth_session)
        auth_url = build_github_auth_url(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"auth_url": auth_url}


@router.get("/auth/github/callback", response_class=HTMLResponse)
def auth_github_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> HTMLResponse:
    target_origin = settings.frontend_origin

    def popup_html(message_type: str, payload: dict) -> HTMLResponse:
        safe_payload = json.dumps(payload)
        safe_type = json.dumps(message_type)
        safe_origin = json.dumps(target_origin)
        html = f"""
<!doctype html>
<html>
  <body style=\"font-family: Arial, sans-serif; padding: 16px;\">
    <p>Completing sign-in...</p>
    <script>
      (function() {{
        const message = {{ type: {safe_type}, payload: {safe_payload} }};
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(message, {safe_origin});
          window.close();
        }} else {{
          document.body.innerText = 'Sign-in complete. You can close this window.';
        }}
      }})();
    </script>
  </body>
</html>
"""
        return HTMLResponse(content=html)

    if error:
        return popup_html("checkers_github_auth_error", {"message": f"GitHub auth failed: {error}"})

    state_payload = consume_github_oauth_state(state or "") if state else None
    if state_payload is None:
        return popup_html("checkers_github_auth_error", {"message": "Invalid or expired OAuth state."})

    if not code:
        return popup_html("checkers_github_auth_error", {"message": "Missing authorization code."})

    try:
        profile = exchange_github_code_for_profile(code)
        user = authenticate_social_user(
            provider="github",
            provider_user_id=str(profile.get("id", "")),
            email=profile.get("email"),
            username=profile.get("login") or profile.get("name"),
        )
        tokens = issue_session_tokens(user)
    except Exception as exc:
        return popup_html("checkers_github_auth_error", {"message": f"GitHub login failed: {str(exc)}"})

    return popup_html(
        "checkers_github_auth_success",
        {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "session_id": tokens["session_id"],
            "expires_in_seconds": tokens["expires_in_seconds"],
            "profile_id": user["profile_id"],
            "username": user.get("username") or "Guest",
            "email": user.get("email"),
            "email_verified": bool(user.get("email_verified")),
            "oauth_session": state_payload.get("oauth_session"),
        },
    )


@router.post("/auth/refresh", response_model=AuthRefreshResponse)
def auth_refresh(payload: AuthRefreshRequest, request: Request) -> dict:
    refreshed = rotate_refresh_token(
        payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    if refreshed is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return refreshed


@router.post("/auth/forgot-password", response_model=AuthForgotPasswordResponse)
def auth_forgot_password(payload: AuthForgotPasswordRequest) -> dict:
    create_password_reset(payload.email)

    return {
        "ok": True,
        "message": "If the account exists, reset instructions were sent by email.",
    }


@router.post("/auth/reset-password", response_model=AuthSimpleResponse)
def auth_reset_password(payload: AuthResetPasswordRequest) -> dict:
    if not reset_password(payload.email, payload.code, payload.new_password):
        raise HTTPException(status_code=400, detail="Invalid reset code, expired code, or weak password")
    return {"ok": True, "message": "Password has been reset"}


@router.post("/auth/logout", response_model=AuthSimpleResponse)
def auth_logout(request: Request) -> dict:
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not revoke_token(token):
        raise HTTPException(status_code=400, detail="Invalid token")

    return {"ok": True, "message": "Logged out"}


@router.get("/auth/sessions", response_model=AuthSessionsResponse)
def auth_sessions(request: Request) -> dict:
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    sessions = list_active_sessions(payload["profile_id"])
    return {"sessions": sessions}


@router.post("/auth/revoke-all", response_model=AuthSimpleResponse)
def auth_revoke_all(payload: AuthRevokeAllRequest, request: Request) -> dict:
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    claims = verify_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    keep_session_id = claims.get("sid") if payload.keep_current else None
    revoked = revoke_all_sessions(claims["profile_id"], keep_session_id=keep_session_id)
    return {"ok": True, "message": f"Revoked {revoked} session(s)."}


@router.post("/auth/revoke-session", response_model=AuthSimpleResponse)
def auth_revoke_session(payload: AuthRevokeSessionRequest, request: Request) -> dict:
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    claims = verify_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    revoked = revoke_session(claims["profile_id"], payload.session_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"ok": True, "message": "Session revoked."}


@router.get("/games/{game_id}/accuracy", response_model=AccuracyScoreResponse)
def get_accuracy_score(game_id: str) -> dict:
    """Get accuracy score and move ratings after game finishes."""
    game = store.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if game.winner is None:
        raise HTTPException(status_code=400, detail="Game not finished yet")
    
    move_history = game.move_history if hasattr(game, "move_history") else []
    return calculate_accuracy_score(game_id, move_history)


@router.post("/puzzle-rush/start", response_model=PuzzleRushStartResponse)
def start_puzzle_rush_session(time_seconds: int = 60, difficulty: str | None = None) -> dict:
    """Start a new Puzzle Rush session with timed puzzles."""
    if time_seconds not in {30, 60, 120, 300}:
        raise HTTPException(status_code=422, detail="time_seconds must be one of 30, 60, 120, 300")

    try:
        return start_puzzle_rush(time_seconds, difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/puzzle-rush/submit", response_model=PuzzleRushResultResponse)
def submit_puzzle_rush(payload: PuzzleRushSubmitRequest) -> dict:
    """Submit solution for a puzzle in Puzzle Rush session."""
    result = submit_puzzle_solution(payload.session_id, payload.puzzle_id, payload.moves)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("error"))

    return {
        "correct": result.get("correct", False),
        "time_taken_seconds": 0.0,
        "score_earned": result.get("score_earned", 0),
        "total_score": result.get("total_score", 0),
        "puzzles_solved": result.get("puzzles_solved", 0),
        "time_remaining": result.get("time_remaining", 0),
        "next_puzzle": result.get("next_puzzle"),
    }


@router.post("/puzzle-rush/finish", response_model=PuzzleRushFinishResponse)
def finish_puzzle_rush_session(session_id: str) -> dict:
    """End Puzzle Rush session and get final score."""
    result = finish_puzzle_rush(session_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.post("/analytics/events", response_model=AnalyticsEventResponse)
def analytics_event(payload: AnalyticsEventRequest, request: Request) -> dict:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    token = extract_bearer_token(auth_header)

    profile_id = payload.profile_id
    if token:
        claims = verify_token(token)
        if claims:
            profile_id = claims.get("profile_id") or profile_id

    try:
        return track_event(
            event_name=payload.event_name,
            profile_id=profile_id,
            game_id=payload.game_id,
            source=payload.source,
            properties=payload.properties,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
def analytics_summary(days: int = 14) -> dict:
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")
    return get_analytics_summary(days)


@router.get("/retention/missions")
def get_missions(profile_id: str) -> dict:
    """Get active missions for a player."""
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    return {"missions": get_active_missions(profile_id)}


@router.post("/retention/missions/issue-daily")
def issue_daily_missions_endpoint(profile_id: str) -> dict:
    """Issue today's daily missions (typically called once per login)."""
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    mission_ids = issue_daily_missions(profile_id)
    return {"issued_count": len(mission_ids), "mission_ids": mission_ids}


@router.post("/retention/missions/issue-weekly")
def issue_weekly_missions_endpoint(profile_id: str) -> dict:
    """Issue this week's weekly missions."""
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    mission_ids = issue_weekly_missions(profile_id)
    return {"issued_count": len(mission_ids), "mission_ids": mission_ids}


@router.get("/retention/achievements")
def get_user_achievements(profile_id: str, limit: int = 10) -> dict:
    """Get recent achievement badges for a player."""
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    return {"achievements": get_achievements(profile_id, limit)}


@router.get("/retention/notifications")
def get_notifications(profile_id: str) -> dict:
    """Get pending notifications for a player."""
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    return {"notifications": get_pending_notifications(profile_id)}


@router.post("/retention/notifications/{notification_id}/read")
def read_notification(notification_id: str) -> dict:
    """Mark a notification as read."""
    if not notification_id:
        raise HTTPException(status_code=400, detail="notification_id is required")
    success = mark_notification_as_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True, "message": "Notification marked as read"}


@router.get("/social/friends", response_model=FriendsListResponse)
def social_friends(request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    return {
        "friends": get_friends(profile_id),
        "pending_requests": get_pending_friend_requests(profile_id),
    }


@router.post("/social/friends/request", response_model=AuthSimpleResponse)
def social_send_friend_request(payload: FriendRequestCreate, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    try:
        send_friend_request(profile_id, payload.target_profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "Friend request sent"}


@router.post("/social/friends/accept", response_model=AuthSimpleResponse)
def social_accept_friend_request(payload: FriendRequestAction, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    accepted = accept_friend_request(profile_id, payload.friendship_id)
    if not accepted:
        raise HTTPException(status_code=404, detail="Friend request not found")
    return {"ok": True, "message": "Friend request accepted"}


@router.delete("/social/friends/{target_profile_id}", response_model=AuthSimpleResponse)
def social_remove_friend(target_profile_id: str, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    removed = remove_friend(profile_id, target_profile_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Friend relationship not found")
    return {"ok": True, "message": "Friend removed"}


@router.post("/social/chat/mute", response_model=AuthSimpleResponse)
def social_chat_mute(payload: ChatMuteRequest, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    try:
        set_mute(profile_id, payload.muted_profile_id, payload.muted)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": "Mute preferences updated"}


@router.get("/social/chat/mute", response_model=ChatMuteListResponse)
def social_chat_mute_list(request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    return {"muted_profile_ids": list_mutes(profile_id)}


@router.get("/social/chat/{game_id}", response_model=ChatMessagesResponse)
def social_chat_messages(game_id: str, request: Request, limit: int = 60) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    return {"messages": list_chat_messages(game_id, viewer_profile_id=profile_id, limit=limit)}


@router.post("/social/chat/{game_id}", response_model=ChatMessageOut)
async def social_chat_create(game_id: str, payload: ChatCreateRequest, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    try:
        message = create_chat_message(game_id, profile_id, payload.text, payload.message_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await realtime.broadcast(game_id, {"type": "chat_message", "message": message})
    return message


@router.post("/social/chat/{message_id}/report", response_model=AuthSimpleResponse)
def social_chat_report(message_id: str, payload: ChatReportRequest, request: Request) -> dict:
    profile_id = _require_profile_id_from_auth(request)
    try:
        ok = report_chat_message(profile_id, message_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True, "message": "Message reported"}


@router.post("/auth/link-provider")
def link_provider(request: Request, payload: AuthSocialLoginRequest) -> dict:
    """Link a social provider to existing account."""
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not payload.provider or payload.provider not in ("google", "github"):
        raise HTTPException(status_code=400, detail="provider must be 'google' or 'github'")

    if not payload.provider_user_id or not payload.email:
        raise HTTPException(status_code=400, detail="provider_user_id and email are required")

    try:
        from sqlalchemy import update
        from app.core.db import SessionLocal

        with SessionLocal() as db:
            updated = db.execute(
                update(AuthUser).where(
                    AuthUser.profile_id == user["profile_id"]
                ).values(
                    social_provider=payload.provider,
                    social_provider_user_id=payload.provider_user_id,
                    social_display_name=payload.username,
                )
            )
            if updated.rowcount == 0:
                raise HTTPException(status_code=404, detail="Auth user not found")
            db.commit()
        return {"ok": True, "message": f"{payload.provider.capitalize()} account linked successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to link provider: {str(exc)}") from exc


@router.delete("/auth/unlink-provider")
def unlink_provider(request: Request, provider: str) -> dict:
    """Unlink a social provider from account."""
    token = extract_bearer_token(request.headers.get("authorization") or request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if provider not in ("google", "github"):
        raise HTTPException(status_code=400, detail="provider must be 'google' or 'github'")

    try:
        from sqlalchemy import update
        from app.core.db import SessionLocal

        with SessionLocal() as db:
            updated = db.execute(
                update(AuthUser).where(
                    AuthUser.profile_id == user["profile_id"],
                    AuthUser.social_provider == provider,
                ).values(
                    social_provider=None,
                    social_provider_user_id=None,
                    social_display_name=None,
                )
            )
            if updated.rowcount == 0:
                raise HTTPException(status_code=404, detail="Linked provider not found")
            db.commit()
        return {"ok": True, "message": f"{provider.capitalize()} account unlinked successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to unlink provider: {str(exc)}") from exc
