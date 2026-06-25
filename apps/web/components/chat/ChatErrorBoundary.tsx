import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ChatErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ChatErrorBoundary caught rendering crash:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-6 border border-red-200 dark:border-red-900/30 bg-red-50/50 dark:bg-red-950/10 rounded-2xl h-full space-y-4">
          <div className="h-10 w-10 rounded-full bg-red-100 dark:bg-red-950 text-red-600 flex items-center justify-center">
            <AlertCircle className="h-5 w-5" />
          </div>
          <div className="text-center space-y-1">
            <h3 className="text-sm font-bold text-slate-800 dark:text-zinc-200">Something went wrong inside the Copilot workspace</h3>
            <p className="text-xs text-slate-400 dark:text-zinc-500 max-w-md mx-auto">
              A rendering failure occurred. Your chat history is preserved in state. Try resetting the UI panel.
            </p>
          </div>
          <button
            type="button"
            onClick={this.handleReset}
            className="flex items-center gap-2 h-10 px-4 bg-slate-900 text-white hover:bg-slate-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 text-xs font-semibold rounded-xl shadow-md transition-all active:scale-[0.98]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset UI Pane
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
