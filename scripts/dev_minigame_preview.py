import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import (
    MINIGAME_STATE_KEY,
    Order,
    _load_order_automation_state,
    _minigame_dev_tools_enabled,
    _minigame_set_state,
    _save_order_automation_state,
    app,
    db,
)


def build_state(result: str, reward_title: str, cycle_order_no: int, global_order_no: int, play_limit: int):
    normalized_result = (result or "lose").strip().lower()
    tier = 0
    winner = normalized_result.startswith("win")
    if winner:
        if normalized_result.endswith("2"):
            tier = 2
        elif normalized_result.endswith("3"):
            tier = 3
        else:
            tier = 1
    return {
        "eligible": True,
        "assigned": True,
        "ready": True,
        "winner": winner,
        "played": False,
        "tier": tier,
        "cycle_order_no": cycle_order_no,
        "global_order_no": global_order_no,
        "result": "pending",
        "message": "Vista previa de desarrollo lista para jugar",
        "assigned_at": datetime.utcnow().isoformat(),
        "played_at": "",
        "reward_item_id": 0,
        "reward_title": reward_title if winner else "",
        "reward_status": "",
        "reward_reference": "",
        "reward_player_name": "",
        "reward_error": "",
        "play_count": 0,
        "play_limit": max(int(play_limit or 1), 1),
        "dev_preview_mode": True,
        "dev_preview_result": normalized_result,
        "dev_preview_reward_title": reward_title if winner else "",
    }


def main():
    parser = argparse.ArgumentParser(description="Arma una orden en modo vista previa del minijuego para desarrollo.")
    parser.add_argument("--order", type=int, default=4, help="ID de la orden a preparar")
    parser.add_argument("--result", default="win1", choices=["lose", "win1", "win2", "win3"], help="Resultado simulado al jugar")
    parser.add_argument("--reward-title", default="Premio de prueba", help="Nombre del premio mostrado en la vista previa ganadora")
    parser.add_argument("--cycle-order", type=int, default=60, help="Posición de orden en el ciclo de 300")
    parser.add_argument("--global-order", type=int, default=60, help="Número global visible en la vista previa")
    parser.add_argument("--attempts", type=int, default=1, help="Cantidad de intentos habilitados para la vista previa")
    parser.add_argument("--clear", action="store_true", help="Limpia la vista previa del minijuego en la orden")
    args = parser.parse_args()

    with app.app_context():
        if not _minigame_dev_tools_enabled():
            raise SystemExit("Vista previa del minijuego deshabilitada fuera de desarrollo.")

        order = Order.query.get(args.order)
        if not order:
            raise SystemExit(f"No existe la orden #{args.order}.")

        if args.clear:
            state = _load_order_automation_state(order)
            if MINIGAME_STATE_KEY in state:
                state.pop(MINIGAME_STATE_KEY, None)
                _save_order_automation_state(order, state)
                db.session.commit()
            print(f"Orden #{order.id} limpiada. La vista previa del minijuego fue removida.")
            return

        preview_state = build_state(args.result, args.reward_title, args.cycle_order, args.global_order, args.attempts)
        _minigame_set_state(order, preview_state)
        db.session.commit()
        print(
            f"Orden #{order.id} lista para vista previa. "
            f"Resultado={args.result}, tier={preview_state['tier'] or 0}, intentos={preview_state['play_limit']}, reward='{preview_state['reward_title']}'."
        )


if __name__ == "__main__":
    main()