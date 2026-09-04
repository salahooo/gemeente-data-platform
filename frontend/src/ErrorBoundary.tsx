import {Component, type ErrorInfo, type ReactNode} from "react";

export class ErrorBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* no sensitive client telemetry */ }
  render() { return this.state.failed ? <main><p role="alert" className="error">Het dashboard kon niet veilig worden weergegeven. Vernieuw de pagina.</p></main> : this.props.children; }
}
