const handshakeCommands = ['wink', 'double blink', 'close your eyes', 'jump'];

export const commands = (handshake) => {
  if (typeof handshake !== 'number') {
    throw new Error('Handshake must be a number');
  }

  const selectedCommands = handshakeCommands.filter(
    (_, bitIndex) => handshake & Math.pow(2, bitIndex),
  );

  const reverseFlag = Math.pow(2, 4);
  const shouldReverse = (handshake & reverseFlag) !== 0;

  // The fifth bit reverses the commands instead of adding another command.
  if (shouldReverse) {
    selectedCommands.reverse();
  }

  return selectedCommands;
};
