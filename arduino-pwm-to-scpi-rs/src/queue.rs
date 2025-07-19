use core::mem::MaybeUninit;

pub struct FixedQueue<T, const N: usize> {
    buffer: [MaybeUninit<T>; N],
    head: usize,    // Index where next item will be dequeued
    tail: usize,    // Index where next item will be enqueued
    len: usize,     // Current number of items
}

impl<T, const N: usize> FixedQueue<T, N> {
    /// Create a new empty queue
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            buffer: unsafe { MaybeUninit::uninit().assume_init() },
            head: 0,
            tail: 0,
            len: 0,
        }
    }

    /// Add an item to the back of the queue
    /// If the queue is full, removes the oldest item first
    /// Returns the removed item if one was displaced, None otherwise
    #[inline(always)]
    pub fn enqueue(&mut self, value: T) {
        if self.len == N {
            // Queue is full, remove the oldest item first
            self.head = (self.head + 1) % N;
            self.len -= 1;
        }

        // Now add the new item
        self.buffer[self.tail] = MaybeUninit::new(value);
        self.tail = (self.tail + 1) % N;
        self.len += 1;

    }

    /// Remove and return the item from the front of the queue
    #[inline(always)]
    pub fn dequeue(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        let value = unsafe { self.buffer[self.head].assume_init_read() };
        self.head = (self.head + 1) % N;
        self.len -= 1;
        Some(value)
    }

    pub fn space(&self) -> usize {
        N - self.len
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    pub fn is_full(&self) -> bool {
        self.len == N
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_queue_is_empty() {
        let queue: FixedQueue<i32, 5> = FixedQueue::new();
        assert!(queue.is_empty());
        assert!(!queue.is_full());
        assert_eq!(queue.len(), 0);
        assert_eq!(queue.space(), 5);
    }

    #[test]
    fn test_enqueue_dequeue_basic() {
        let mut queue: FixedQueue<i32, 3> = FixedQueue::new();
        
        queue.enqueue(1);
        assert_eq!(queue.len(), 1);
        assert_eq!(queue.space(), 2);
        assert!(!queue.is_empty());
        
        queue.enqueue(2);
        queue.enqueue(3);
        assert!(queue.is_full());
        assert_eq!(queue.len(), 3);
        assert_eq!(queue.space(), 0);
        
        assert_eq!(queue.dequeue(), Some(1));
        assert_eq!(queue.dequeue(), Some(2));
        assert_eq!(queue.dequeue(), Some(3));
        assert_eq!(queue.dequeue(), None);
        assert!(queue.is_empty());
    }

    #[test]
    fn test_circular_buffer_behavior() {
        let mut queue: FixedQueue<i32, 3> = FixedQueue::new();
        
        // Fill the queue
        queue.enqueue(1);
        queue.enqueue(2);
        queue.enqueue(3);
        
        // Add one more - should wrap around and displace oldest
        queue.enqueue(4);
        
        // Should now contain [2, 3, 4]
        assert_eq!(queue.dequeue(), Some(2));
        assert_eq!(queue.dequeue(), Some(3));
        assert_eq!(queue.dequeue(), Some(4));
        assert_eq!(queue.dequeue(), None);
    }

    #[test]
    fn test_alternating_enqueue_dequeue() {
        let mut queue: FixedQueue<i32, 2> = FixedQueue::new();
        
        queue.enqueue(1);
        assert_eq!(queue.dequeue(), Some(1));
        
        queue.enqueue(2);
        queue.enqueue(3);
        assert_eq!(queue.dequeue(), Some(2));
        
        queue.enqueue(4);
        assert_eq!(queue.dequeue(), Some(3));
        assert_eq!(queue.dequeue(), Some(4));
        assert!(queue.is_empty());
    }

    #[test]
    fn test_wrap_around_indices() {
        let mut queue: FixedQueue<i32, 2> = FixedQueue::new();
        
        // Exercise the circular buffer multiple times
        for i in 0..10 {
            queue.enqueue(i);
            if i >= 2 {
                queue.enqueue(i + 1);
                // Queue should contain the last 2 values
                assert_eq!(queue.dequeue(), Some(i));
                assert_eq!(queue.dequeue(), Some(i + 1));
            }
        }
    }

    #[test]
    fn test_with_strings() {
        let mut queue: FixedQueue<String, 2> = FixedQueue::new();
        
        queue.enqueue("hello".to_string());
        queue.enqueue("world".to_string());
        queue.enqueue("rust".to_string()); // Should displace "hello"
        
        assert_eq!(queue.dequeue(), Some("world".to_string()));
        assert_eq!(queue.dequeue(), Some("rust".to_string()));
        assert_eq!(queue.dequeue(), None);
    }

    #[test]
    fn test_single_element_queue() {
        let mut queue: FixedQueue<i32, 1> = FixedQueue::new();
        
        queue.enqueue(42);
        assert!(queue.is_full());
        assert_eq!(queue.len(), 1);
        
        queue.enqueue(43); // Should replace 42
        assert_eq!(queue.dequeue(), Some(43));
        assert!(queue.is_empty());
    }

    #[test]
    fn test_zero_sized_types() {
        let mut queue: FixedQueue<(), 3> = FixedQueue::new();
        
        queue.enqueue(());
        queue.enqueue(());
        assert_eq!(queue.len(), 2);
        
        assert_eq!(queue.dequeue(), Some(()));
        assert_eq!(queue.dequeue(), Some(()));
        assert_eq!(queue.dequeue(), None);
    }
}