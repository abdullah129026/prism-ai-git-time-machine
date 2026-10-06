"use client";

import { Component, type ReactNode } from "react";
import { RotateCcw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** What crashed, e.g. "3D scene". */
  label: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Catches render crashes (e.g. WebGL blowing up) and offers a retry
 *  instead of a blank pane. */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  render() {
    const { error } = this.state;
    if (error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm text-ink">
            The {this.props.label} ran into a problem.
          </p>
          <p className="max-w-md font-mono text-xs text-danger">
            {error.message}
          </p>
          <button
            className="btn-quiet"
            onClick={() => this.setState({ error: null })}
          >
            <RotateCcw size={14} />
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
