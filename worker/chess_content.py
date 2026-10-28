"""Legal chess positions and SVG boards, built with python-chess."""
import chess
import chess.svg


def prepare_chess(card):
    position = card.get("chess")
    if not position:
        return
    board = chess.Board(position["fen"])
    if not board.is_valid():
        raise ValueError("Invalid chess position")
    original = board.copy()
    quiz = card.get("quiz")
    if quiz and (not position["line"] or quiz["options"][quiz["correct_index"]] != position["line"][0]):
        raise ValueError("Chess puzzle answer must match its first continuation move")
    for san in position["line"]:
        move = board.parse_san(san)
        if board.san(move) != san:
            raise ValueError("Chess continuation must use accurate SAN, including check/mate")
        board.push(move)
    # Never trust SVG returned by a model. Render only the validated start board.
    position["svg"] = chess.svg.board(original, size=390, coordinates=True,
                                       orientation=original.turn)


def build_bank():
    cards = []
    def add(key, moves, title, body, solution=None, options=None, line=()):
        board = chess.Board()
        for move in moves.split():
            board.push_san(move)
        card = dict(id="chess_italian_" + key, created_at="2026-10-28T12:00:00Z",
                    category="INTEREST", course_tag=None, topic="chess", title=title,
                    body_markdown=body, solution_markdown=solution, source_url=None,
                    parent_card_id=None, comments=[], diagram=None, quiz=None,
                    chess={"fen": board.fen(), "line": list(line)})
        if options:
            card["quiz"] = {"options": options, "correct_index": 0}
        prepare_chess(card)
        cards.append(card)

    italian = "e4 e5 Nf3 Nc6 Bc4"
    add("starting_point", italian, "Italian Game: what 3.Bc4 actually does",
        "After **1.e4 e5 2.Nf3 Nc6 3.Bc4**, White develops with an eye on f7, the pawn initially defended only by Black's king. That pressure is a theme, not permission to sacrifice immediately.\n\nBlack's **3...Bc5** leads to the Giuoco Piano; **3...Nf6** enters the Two Knights Defense. Learn both branches rather than memorizing one cooperative sequence.")
    add("quiet_plan", italian + " Bc5 c3 Nf6 d3", "The quiet Italian: why c3 and d3 belong together",
        "In this quiet Italian structure, **c3** supports a future d4 and leaves c2 available for a bishop retreat. **d3** supports e4 and opens the c1 bishop. White can castle, develop the queenside, and prepare d4 when the center is ready.\n\nA common maneuver is Nb1-d2-f1-g3 after castling and moving the f1 rook. It is a plan to evaluate, not an automatic script: watch Black's ...d5 break.")
    add("central_break", italian + " Bc5 c3 Nf6", "Italian move-order check: what did c3 prepare?",
        "White to move after 1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6. Which pawn move immediately challenges e5 and attacks the bishop on c5?",
        "**5.d4** attacks both e5 and the c5 bishop.\nAfter **5...exd4 6.cxd4**, White has a central pawn duo; Black can answer **6...Bb4+**, so calculate before assuming the center is secure.",
        ["d4", "a3", "h3", "b3"], ["d4", "exd4", "cxd4", "Bb4+"])
    add("fork", italian + " Nf6 Ng5 d5 exd5 Nxd5", "Two Knights puzzle: spot the fork on f7",
        "White to move after 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5 d5 5.exd5 Nxd5. Which knight move attacks the queen on d8 and rook on h8 at the same time?",
        "**6.Nxf7** forks the queen on d8 and rook on h8; it is not check.\nBlack can play **6...Kxf7**, accepting the Fried Liver sacrifice. After **7.Qf3+**, White attacks the exposed king. A fork is not automatically a free piece!",
        ["Nxf7", "Ne6", "Nh3", "Nf3"], ["Nxf7", "Kxf7", "Qf3+"])
    add("na5", italian + " Nf6 Ng5 d5 exd5", "Two Knights: attack the bishop instead of recapturing",
        "Black to move. Which move by the c6 knight attacks White's bishop on c4 immediately, offering a pawn rather than entering 5...Nxd5 6.Nxf7?",
        "**5...Na5** attacks the bishop on c4.\nAfter **6.Bb5+ c6 7.dxc6 bxc6**, Black has development and central activity as compensation for a pawn; this is a position to study, not a forced win.",
        ["Na5", "Nb8", "Ne7", "Nb4"], ["Na5", "Bb5+", "c6", "dxc6", "bxc6"])
    add("f7_caution", italian + " Nf6 Ng5 d5 exd5 Nxd5 Nxf7 Kxf7", "Fried Liver: a fork can also be a sacrifice",
        "The board shows **6...Kxf7** after White's Nxf7 fork. Black's knight on d5 blocks the c4 bishop's diagonal, so the king capture is legal. White continues **7.Qf3+**, developing with check and attacking d5.\n\nStudy this as an attack requiring calculation. The phrase 'f7 is weak' does not establish that a sacrifice wins, and legal-move validation alone does not prove the best move.", line=["Qf3+"])
    import random
    for card in cards:
        if card["quiz"]:
            quiz = card["quiz"]
            answer = quiz["options"][0]
            random.Random(card["id"]).shuffle(quiz["options"])
            quiz["correct_index"] = quiz["options"].index(answer)
    return cards


if __name__ == "__main__":
    from .run_pipeline import FEED_PATH, _load_feed, merge_feed, atomic_write
    feed = _load_feed(FEED_PATH)
    atomic_write(FEED_PATH, merge_feed(feed, new_cards=build_bank(), replies=[], issues=[], calendar=feed))
