import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeEach } from "vitest";

type ConsoleArgs = Parameters<typeof console.error>;

const originalError = console.error;
const originalWarn = console.warn;

let errorBuffer: ConsoleArgs[] = [];
let warnBuffer: ConsoleArgs[] = [];

console.error = (...args: ConsoleArgs) => {
  errorBuffer.push(args);
};

console.warn = (...args: ConsoleArgs) => {
  warnBuffer.push(args);
};

beforeEach(() => {
  errorBuffer = [];
  warnBuffer = [];
});

afterEach((context) => {
  if (context.task.result?.state === "fail") {
    errorBuffer.forEach((args) => originalError(...args));
    warnBuffer.forEach((args) => originalWarn(...args));
  }

  cleanup();
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});
