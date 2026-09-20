import { Component, type ErrorInfo, type ReactNode } from "react";
import { GlassCard } from "./GlassCard";

type Props = { children: ReactNode };
type State = { error?: Error };

export class ErrorBoundary extends Component<Props, State> {
  state: State = {};

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <GlassCard className="p-6 text-sm text-amber-200">
          This view crashed ({this.state.error.message}). Reload the page or open another tab.
        </GlassCard>
      );
    }
    return this.props.children;
  }
}
