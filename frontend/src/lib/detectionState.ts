import type { DetectionResponse } from "./detection";

export interface DetectionState {
  result: DetectionResponse | null;
  errorMessage: string | null;
  isAnalyzing: boolean;
  latestRequestId: number;
}

export type DetectionAction =
  | { type: "request_started"; requestId: number; clearResult?: boolean }
  | { type: "request_succeeded"; requestId: number; result: DetectionResponse }
  | { type: "request_failed"; requestId: number; message: string; clearResult?: boolean }
  | { type: "request_invalidated"; requestId: number; clearResult?: boolean }
  | { type: "reset"; requestId: number }
  | { type: "set_error"; requestId: number; message: string }
  | { type: "clear_error" };

export const initialDetectionState: DetectionState = {
  result: null,
  errorMessage: null,
  isAnalyzing: false,
  latestRequestId: 0,
};

export function detectionReducer(state: DetectionState, action: DetectionAction): DetectionState {
  switch (action.type) {
    case "request_started":
      if (action.requestId <= state.latestRequestId) return state;
      return {
        ...state,
        latestRequestId: action.requestId,
        result: action.clearResult ? null : state.result,
        errorMessage: null,
        isAnalyzing: true,
      };
    case "request_succeeded":
      if (action.requestId !== state.latestRequestId) return state;
      return { ...state, result: action.result, errorMessage: null, isAnalyzing: false };
    case "request_failed":
      if (action.requestId !== state.latestRequestId) return state;
      return {
        ...state,
        result: action.clearResult ? null : state.result,
        errorMessage: action.message,
        isAnalyzing: false,
      };
    case "request_invalidated":
      if (action.requestId <= state.latestRequestId) return state;
      return {
        ...state,
        latestRequestId: action.requestId,
        result: action.clearResult ? null : state.result,
        errorMessage: action.clearResult ? null : state.errorMessage,
        isAnalyzing: false,
      };
    case "reset":
      if (action.requestId <= state.latestRequestId) return state;
      return { ...initialDetectionState, latestRequestId: action.requestId };
    case "set_error":
      if (action.requestId < state.latestRequestId) return state;
      return { ...state, latestRequestId: action.requestId, errorMessage: action.message, isAnalyzing: false };
    case "clear_error":
      return { ...state, errorMessage: null };
  }
}
