
pub struct RingBuffer<const N: usize> {
    buffer: [u16; N],
    head: u8,
    sum: u16,
    count: u8,
}

impl<const N: usize> RingBuffer<N> {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            //buffer: unsafe { MaybeUninit::uninit().assume_init() },
            buffer: [0; N],
            head: 0,
            sum: 0,
            count: 0,
        }
    }

    #[inline(always)]
    pub fn push(&mut self, value: u16) {
        if (self.count as usize) < N {
            // Buffer not full yet
            self.buffer[self.head as usize] = value;
            self.sum = self.sum + value;
            self.count += 1;
        } else {
            // Buffer is full, replace oldest value
            let old_value = self.buffer[self.head as usize];
            self.buffer[self.head as usize] = value;
            self.sum = self.sum - old_value + value;
        }
        
        // Advance head pointer with wraparound
        self.head = ((self.head + 1) as usize % N) as u8;
    }

    #[inline(always)]
    pub fn average(&self) -> Option<u16> {
        if self.count == 0 {
            None
        } else {
            Some(self.sum / self.count as u16)
        }
    }

    #[inline(always)]
    pub fn sum(&self) -> u16 {
        self.sum
    }

    #[inline(always)]
    pub fn len(&self) -> u8 {
        self.count
    }

    #[inline(always)]
    pub fn is_full(&self) -> bool {
        self.count as usize == N
    }

    #[inline(always)]
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }

    #[inline(always)]
    pub fn clear(&mut self) {
        self.head = 0;
        self.count = 0;
        self.sum = 0;
        // Note: We don't need to clear the buffer array since we track count
    }

    pub fn all_same(&self)->bool{
        if (self.count as usize) < N {
            false
        }else{
            let first = self.buffer[0];
            for i in &self.buffer[1..]{
                if *i != first{
                    return false
                }
            }
            true
        }
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_buffer_is_empty() {
        let buffer: RingBuffer<5> = RingBuffer::new();
        assert!(buffer.is_empty());
        assert!(!buffer.is_full());
        assert_eq!(buffer.len(), 0);
        assert_eq!(buffer.sum(), 0);
        assert_eq!(buffer.average(), None);
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_push_single_value() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(10);
        assert_eq!(buffer.len(), 1);
        assert_eq!(buffer.sum(), 10);
        assert_eq!(buffer.average(), Some(10));
        assert!(!buffer.is_empty());
        assert!(!buffer.is_full());
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_push_multiple_values() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(10);
        buffer.push(20);
        buffer.push(30);
        
        assert!(buffer.is_full());
        assert_eq!(buffer.len(), 3);
        assert_eq!(buffer.sum(), 60);
        assert_eq!(buffer.average(), Some(20));
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_overflow_behavior() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        // Fill buffer
        buffer.push(10);
        buffer.push(20);
        buffer.push(30);
        assert_eq!(buffer.sum(), 60);
        assert_eq!(buffer.average(), Some(20));
        
        // Add fourth value - should replace first (10)
        buffer.push(40);
        assert_eq!(buffer.sum(), 90); // 20 + 30 + 40
        assert_eq!(buffer.average(), Some(30));
        assert_eq!(buffer.len(), 3);
        assert!(buffer.is_full());
        
        // Add fifth value - should replace second (20)
        buffer.push(50);
        assert_eq!(buffer.sum(), 120); // 30 + 40 + 50
        assert_eq!(buffer.average(), Some(40));
    }

    #[test]
    fn test_wraparound_indexing() {
        let mut buffer: RingBuffer<2> = RingBuffer::new();
        
        // Fill and overflow multiple times
        buffer.push(1);
        buffer.push(2);
        assert_eq!(buffer.sum(), 3);
        
        buffer.push(3); // replaces 1
        assert_eq!(buffer.sum(), 5); // 2 + 3
        
        buffer.push(4); // replaces 2
        assert_eq!(buffer.sum(), 7); // 3 + 4
        
        buffer.push(5); // replaces 3
        assert_eq!(buffer.sum(), 9); // 4 + 5
        
        assert_eq!(buffer.len(), 2);
        assert!(buffer.is_full());
    }

    #[test]
    fn test_average_calculation() {
        let mut buffer: RingBuffer<4> = RingBuffer::new();
        
        buffer.push(10);
        assert_eq!(buffer.average(), Some(10));
        
        buffer.push(20);
        assert_eq!(buffer.average(), Some(15)); // (10 + 20) / 2
        
        buffer.push(30);
        assert_eq!(buffer.average(), Some(20)); // (10 + 20 + 30) / 3
        
        buffer.push(40);
        assert_eq!(buffer.average(), Some(25)); // (10 + 20 + 30 + 40) / 4
        
        // Overflow - replace 10 with 50
        buffer.push(50);
        assert_eq!(buffer.average(), Some(35)); // (20 + 30 + 40 + 50) / 4
    }

    #[test]
    fn test_clear() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(10);
        buffer.push(20);
        buffer.push(30);
        
        assert!(!buffer.is_empty());
        assert_eq!(buffer.sum(), 60);
        
        buffer.clear();
        
        assert!(buffer.is_empty());
        assert!(!buffer.is_full());
        assert_eq!(buffer.len(), 0);
        assert_eq!(buffer.sum(), 0);
        assert_eq!(buffer.average(), None);
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_all_same_empty_buffer() {
        let buffer: RingBuffer<3> = RingBuffer::new();
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_all_same_partial_buffer() {
        let mut buffer: RingBuffer<4> = RingBuffer::new();
        
        buffer.push(10);
        buffer.push(10);
        buffer.push(10);
        
        // Not full, so all_same should return false
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_all_same_full_buffer_same_values() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(42);
        buffer.push(42);
        buffer.push(42);
        
        assert!(buffer.all_same());
    }

    #[test]
    fn test_all_same_full_buffer_different_values() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(10);
        buffer.push(20);
        buffer.push(10);
        
        assert!(!buffer.all_same());
    }

    #[test]
    fn test_all_same_after_overflow() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        // Fill with different values
        buffer.push(10);
        buffer.push(20);
        buffer.push(30);
        assert!(!buffer.all_same());
        
        // Overflow with same values
        buffer.push(50);
        buffer.push(50);
        buffer.push(50);
        assert!(buffer.all_same());
    }

    #[test]
    fn test_single_element_buffer() {
        let mut buffer: RingBuffer<1> = RingBuffer::new();
        
        buffer.push(42);
        assert!(buffer.is_full());
        assert_eq!(buffer.len(), 1);
        assert_eq!(buffer.sum(), 42);
        assert_eq!(buffer.average(), Some(42));
        assert!(buffer.all_same());
        
        buffer.push(100);
        assert_eq!(buffer.sum(), 100);
        assert_eq!(buffer.average(), Some(100));
        assert!(buffer.all_same());
    }

    #[test]
    fn test_zero_values() {
        let mut buffer: RingBuffer<3> = RingBuffer::new();
        
        buffer.push(0);
        buffer.push(0);
        buffer.push(0);
        
        assert_eq!(buffer.sum(), 0);
        assert_eq!(buffer.average(), Some(0));
        assert!(buffer.all_same());
    }

    #[test]
    fn test_edge_case_buffer_size_255() {
        // Test with buffer size that matches u8::MAX
        let mut buffer: RingBuffer<255> = RingBuffer::new();
        
        // Fill partially
        for i in 0..100 {
            buffer.push(i);
        }
        
        assert_eq!(buffer.len(), 100);
        assert!(!buffer.is_full());
        
        // Fill completely
        for i in 100..255 {
            buffer.push(i);
        }
        
        assert_eq!(buffer.len(), 255);
        assert!(buffer.is_full());
    }

    #[test]
    fn test_head_pointer_wraparound() {
        let mut buffer: RingBuffer<2> = RingBuffer::new();
        
        // Test that head pointer wraps correctly
        buffer.push(1);
        buffer.push(2);
        // head should be 0 now (wrapped)
        
        buffer.push(3); // Should replace buffer[0] (value 1)
        buffer.push(4); // Should replace buffer[1] (value 2)
        
        // Buffer should now contain [3, 4]
        assert_eq!(buffer.sum(), 7);
        assert_eq!(buffer.len(), 2);
        assert!(buffer.is_full());
    }
}