(* Exercise 3: tank-heating process (PLC exercise Task 2) in IEC 61131-3 Structured Text.
   Same state machine as tank_fsm.py. Written for a Siemens S7-1200/1500 FB in TIA Portal (SCL),
   using standard IEC timers. Not downloaded to hardware: the Python file is the tested model. *)

FUNCTION_BLOCK FB_Tank
VAR_INPUT
    Start : BOOL;      (* S1 start button          *)
    B1    : BOOL;      (* level sensor low         *)
    B2    : BOOL;      (* level sensor middle      *)
    B3    : BOOL;      (* level sensor high        *)
END_VAR
VAR_OUTPUT
    M1 : BOOL;         (* pump motor fill (G1)     *)
    M2 : BOOL;         (* pump motor drain (G2)    *)
    E1 : BOOL;         (* heater                   *)
    Cycle : INT;       (* completed cycles         *)
END_VAR
VAR
    State   : INT := 0;    (* 0 IDLE, 1 FILL, 2 HEAT_HOLD, 3 DRAIN, 4 MAINTENANCE *)
    tHeat   : TON;
    tMaint  : TON;
END_VAR
VAR CONSTANT
    IDLE : INT := 0; FILL : INT := 1; HEAT_HOLD : INT := 2; DRAIN : INT := 3; MAINTENANCE : INT := 4;
    CYCLES : INT := 5;
END_VAR

tHeat(IN := State = HEAT_HOLD, PT := T#20S);
tMaint(IN := State = MAINTENANCE, PT := T#90S);

CASE State OF
    IDLE:
        IF Start AND NOT B1 THEN
            State := FILL;
        END_IF;
    FILL:
        IF B3 THEN
            State := HEAT_HOLD;
        END_IF;
    HEAT_HOLD:
        IF tHeat.Q THEN
            State := DRAIN;
        END_IF;
    DRAIN:
        IF NOT B1 THEN
            Cycle := Cycle + 1;
            IF Cycle < CYCLES THEN
                State := FILL;
            ELSE
                State := MAINTENANCE;
            END_IF;
        END_IF;
    MAINTENANCE:
        IF tMaint.Q THEN
            Cycle := 0;
            State := IDLE;
        END_IF;
END_CASE;

(* Moore outputs, plus the B2 condition for the heater while filling *)
M1 := State = FILL;
M2 := State = DRAIN;
E1 := (State = FILL AND B2) OR State = HEAT_HOLD;

END_FUNCTION_BLOCK
