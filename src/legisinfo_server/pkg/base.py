from abc import ABC, abstractmethod


class BaseService[ReturnSchema](ABC):
    @abstractmethod
    async def perform(self) -> ReturnSchema:
        """Execute the service and return the structured result."""
        pass
